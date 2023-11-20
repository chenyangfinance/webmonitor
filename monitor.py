import os
import pickle
import smtplib
import ssl
from email.mime.text import MIMEText
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
import re

load_dotenv()

def sanitize_filename(url):
    # Use regular expressions to replace invalid filename characters with underscores
    return re.sub(r'[\/:*?"<>|]', '_', url)

def fetch_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text

        # Parse the HTML and extract the text
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()

        return text
    except requests.exceptions.RequestException as e:
        # If an exception occurs (e.g., invalid URL or website not reachable), return None
        print(f"Error fetching content for {url}: {e}")
        return None

def send_email(recipients, subject, body):
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = os.environ["EMAIL_ADDRESS"]
    message["To"] = ", ".join(recipients)

    text = MIMEText(body, "plain")
    message.attach(text)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(os.environ["SMTP_SERVER"], os.environ["SMTP_PORT"], context=context) as server:
        server.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_PASSWORD"])
        server.sendmail(os.environ["EMAIL_ADDRESS"], recipients, message.as_string())

def save_content(file_name, content):
    with open(file_name, 'wb') as f:
        pickle.dump(content, f)

def send_invalid_url_email(receiver_email, url, status_code):
    subject = f"Website {url} is invalid or removed"
    body = f"The website {url} returned an HTTP status code {status_code}. Please check if the website is still valid or has been removed."
    send_email(receiver_email, subject, body)

def load_content(file_name):
    if os.path.exists(file_name):
        with open(file_name, 'rb') as f:
            return pickle.load(f)
    return None

def load_urls_from_file(file_name):
    with open(file_name, 'r') as f:
        # Filter out empty lines and strip leading/trailing whitespace from URLs
        urls = [line.strip() for line in f if line.strip()]

        # Remove duplicates by converting the list to a set and then back to a list
        unique_urls = list(set(urls))

    # Save the unique URLs back to the file
    with open(file_name, 'w') as f:
        for url in unique_urls:
            f.write(url + '\n')

    return unique_urls

def send_invalid_url_email(receiver_email, url, status_code):
    subject = f"Website {url} is invalid or removed"
    body = f"The website {url} returned an HTTP status code {status_code}. Please check if the website is still valid or has been removed."
    send_email(receiver_email, subject, body)


def load_recipients_from_file(file_name):
    with open(file_name, 'r') as f:
        return [line.strip() for line in f]

def monitor_websites(websites, recipients):
    pickles_folder = "website_pickles"
    if not os.path.exists(pickles_folder):
        os.makedirs(pickles_folder)

    for url in websites:
        # Define the sanitized file name to store the website content
        sanitized_url = sanitize_filename(url)
        file_name = f"{pickles_folder}/{sanitized_url}.pickle"

        # Fetch the new content and check for invalid URL
        new_content = fetch_content(url)

        if new_content is None:
            # Notify about invalid or removed website
            send_invalid_url_email(recipients, url, 0)
            continue  # Skip further processing for this website

        # Load the previous content
        old_content = load_content(file_name)

        # If there's no previous content, save the content without sending an email
        if old_content is None:
            save_content(file_name, new_content)
        else:
            # Compare the word count difference
            old_word_count = len(old_content.split())
            new_word_count = len(new_content.split())

            # If the word count difference is 3 or more, send an email
            if abs(new_word_count - old_word_count) >= 3:
                print(f"The website {url} has been updated.")
                send_email(
                    recipients,
                    f"Website update: {url}",
                    f"The website {url} has been updated.",
                )

                # Save the new content for future comparisons
                save_content(file_name, new_content)

if __name__ == "__main__":
    websites = load_urls_from_file("websites.txt")
    recipients = load_recipients_from_file("recipients.txt")

    monitor_websites(websites, recipients)