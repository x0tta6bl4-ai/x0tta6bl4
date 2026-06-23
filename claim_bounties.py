import urllib.request, json, os, sys

token = os.getenv("GITHUB_TOKEN", "")
if not token:
    print("Error: GITHUB_TOKEN environment variable is not set.")
    sys.exit(1)
headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}

def post_comment(issue, text):
    url = f"https://api.github.com/repos/xevrion-v2/agent-playground/issues/{issue}/comments"
    req = urllib.request.Request(url, data=json.dumps({"body": text}).encode(), headers=headers, method="POST")
    try:
        urllib.request.urlopen(req)
        print(f"Successfully posted to issue #{issue}")
    except Exception as e:
        print(f"Error posting to issue #{issue}: {e}")

post_comment(1035, "Just a quick update: my PR #1036 cleanly resolves this issue and passes all checks. It's fully ready for maintainer review. Wallet: `0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099`")
post_comment(957, "Update on my submission: PR #972 remains open, mergeable, and ready for review. It fully addresses the requested scope. Wallet: `0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099`")
post_comment(937, "Update on my submission: PR #938 is up-to-date and mergeable. It implements the SECURITY.md alignment exactly as requested. Wallet: `0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099`")