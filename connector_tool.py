from cachetools import TTLCache
import requests

# 1. Define the ephemeral cache at the module level.
# maxsize: limits memory footprint. 
# ttl: sets the token lifespan (e.g., 3600 seconds / 1 hour to match an ADFS session).
# Once the TTL expires, the token is automatically purged from memory.
session_tokens = TTLCache(maxsize=1000, ttl=3600)

class Tools:
    def __init__(self):
        # Confluence OAuth credentials (injected via Open WebUI environment variables)
        self.client_id = "YOUR_CLIENT_ID"
        self.client_secret = "YOUR_CLIENT_SECRET"
        self.redirect_uri = "https://your-openwebui-domain.com" # Can just be the homepage

    def run(self, query: str, __user__: dict) -> str:
        # The ADFS identifier is our primary key
        user_id = __user__["id"] 
        
        # 2. Check the ephemeral cache
        access_token = session_tokens.get(user_id)

        # 3. Intercept an Authorization Code (The Callback)
        # If the user pastes the code from Confluence into the chat, intercept it.
        if "code=" in query:
            extracted_code = query.split("code=")[1].strip()
            
            # Exchange the code for the Confluence Access Token
            token_response = requests.post(
                "https://your-confluence-domain.atlassian.net/plugins/servlet/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": extracted_code,
                    "redirect_uri": self.redirect_uri
                }
            )
            
            if token_response.status_code == 200:
                access_token = token_response.json().get("access_token")
                # Store it in the TTL cache mapped to the ADFS user
                session_tokens[user_id] = access_token
                return "Session authorized. I am connected to Confluence. What would you like to search?"
            else:
                return f"Failed to authorize: {token_response.text}"

        # 4. Enforce Authorization
        # If the token doesn't exist (or expired), halt and prompt the user.
        if not access_token:
            auth_url = (
                f"https://your-confluence-domain.atlassian.net/plugins/servlet/oauth2/authorize"
                f"?client_id={self.client_id}&response_type=code&redirect_uri={self.redirect_uri}"
            )
            return (
                f"I need temporary permission to search Confluence for this session.\n\n"
                f"1. [Click here to authorize]({auth_url})\n"
                f"2. Confluence will redirect you. Copy the `code=...` parameter from the URL.\n"
                f"3. Paste `code=YOUR_CODE` back into this chat."
            )

        # 5. Execute the Confluence API Call
        # If we reach here, we have a valid, in-memory session token.
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        search_response = requests.get(
            f"https://your-confluence-domain.atlassian.net/wiki/rest/api/search?cql=text~\"{query}\"",
            headers=headers
        )
        
        # Parse and return your Confluence data
        return str(search_response.json())
