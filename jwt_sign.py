import jwt
import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()


def get_secret():
    token = os.getenv('JWT_SECRET')
    if not token:
        # Fallback development secret — warn the user
        print("Warning: JWT_SECRET not found in environment. Using development fallback secret.", file=sys.stderr)
        token = "dev_secret_change_me"
    return token


def build_payload(role: str) -> dict:
    return {
        "role": role,
        "iss": "supabase",
        # Keep original iat/exp constants from the previous script
        "iat": 1758211200,
        "exp": 1915977600,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a JWT for Supabase-like service roles.")
    parser.add_argument(
        "--role",
        choices=["service_role", "anon"],
        help="Role to embed in the token (service_role or anon). If omitted, you'll be prompted.",
    )
    parser.add_argument(
        "--choice",
        choices=["1", "2"],
        help="Numeric choice for role: 1 -> service_role, 2 -> anon (interactive or for scripts).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    role = args.role
    # If numeric choice provided, map it
    if getattr(args, 'choice', None):
        if args.choice == '1':
            role = 'service_role'
        elif args.choice == '2':
            role = 'anon'
    if not role:
        # Interactive prompt with numeric options
        try:
            inp = input("Choose role: 1) service_role  2) anon  : ").strip()
        except EOFError:
            inp = ""
        if inp == '2':
            role = 'anon'
        else:
            role = 'service_role'
    if role not in ("service_role", "anon"):
        print("Invalid role. Choose 'service_role' or 'anon'.", file=sys.stderr)
        sys.exit(1)

    secret = get_secret()
    payload = build_payload(role)
    token = jwt.encode(payload, secret, algorithm="HS256")
    # jwt.encode may return bytes in some versions — ensure we print str
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    # Print a descriptive line and then the token on its own line
    print(f"Role: {role}")
    print(token)


if __name__ == '__main__':
    main()