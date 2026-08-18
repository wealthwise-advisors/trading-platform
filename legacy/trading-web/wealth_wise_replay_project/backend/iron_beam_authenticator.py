import json
import requests


class IronbeamAuthenticator:
    """
    A class to handle authentication with the Ironbeam API and fetch a Bearer token.
    """

    def __init__(self, account_id, password, api_key):
        """
        Initialize the IronbeamAuthenticator with account credentials and API key.
        """
        self.account_id = account_id
        self.password = password
        self.api_key = api_key
        self.base_url = "https://live.ironbeamapi.com"
        self.bearer_token = None


    def authenticate(self):
        """
        Authenticate the user and fetch the Bearer token.
        :return: The Bearer token if authentication is successful, otherwise None.
        """
        url = f"{self.base_url}/v2/auth"
        payload = {
            "username": self.account_id,
            "apiKey": self.api_key
        }
        headers = {"Content-Type": "application/json"}

        # Print the full request details
        print("Sending authentication request:")
        print("URL:", url)
        print("Headers:", json.dumps(headers, indent=4))
        print("Payload:", json.dumps(payload, indent=4))

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            self.bearer_token = data.get('token')
            if self.bearer_token:
                print("Authentication successful. Token:", self.bearer_token)
                return self.bearer_token
            else:
                print("Authentication failed. Token not found.")
                return None
        except requests.exceptions.RequestException as e:
            print("Error during authentication:", e)
            return None
        except ValueError:
            print("Failed to parse JSON response during authentication.")
            return None


# Example Usage
if __name__ == "__main__":
    # Replace with your actual credentials and API key
    account_id = "23087442"
    password = "empire786110"
    api_key = "REDACTED__see_legacy_REDACTIONS_md"

    # Initialize the authenticator
    authenticator = IronbeamAuthenticator(account_id, password, api_key)

    # Authenticate and fetch the Bearer token
    token = authenticator.authenticate()

    # Use the token in your application if authentication is successful
    if token:
        print("Bearer token is ready for use.")
    else:
        print("Failed to authenticate.")
