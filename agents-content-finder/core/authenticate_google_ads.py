from google_auth_oauthlib.flow import InstalledAppFlow

# STEP 1: Must match the client_secrets.json you downloaded from Google Cloud Console
SCOPES = ["https://www.googleapis.com/auth/adwords"]

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        './core/google_ads_client_secret.json',  # <-- This must be in your repo
        scopes=SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )

    # Generate auth URL
    auth_url, _ = flow.authorization_url(prompt='consent')
    print("🔗 Please visit this URL in your browser:\n")
    print(auth_url)

    # Ask user to paste the code from the redirect page
    code = input("\n📥 Enter the authorization code here: ")
    flow.fetch_token(code=code)

    print("\n✅ Your refresh token is:\n")
    print(flow.credentials.refresh_token)


if __name__ == "__main__":
    main()
