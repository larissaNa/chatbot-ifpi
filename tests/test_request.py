import requests
import json

def main():
    url = "http://localhost/chatbot"
    headers = {"Content-Type": "application/json"}

    questions = [
        "Quais são as normas do IFPI?",
        "Quem é o presidente do Brasil?",
    ]

    for q in questions:
        print(f"Testing question: {q}")
        payload = {"message": q}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            print(f"Status Code: {response.status_code}")
            if response.status_code != 200:
                print("Response Body:")
                print(response.text)
            else:
                print("Success")
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 20)


if __name__ == "__main__":
    main()
