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
from difflib import SequenceMatcher
import time
import random

load_dotenv()

SCHOLAR_KEYWORDS = {
    'revise_resubmit': ['and resubmit', 'r&r', '& resubmit', '&resubmit'],
    'forthcoming': ['forthcoming','accepted'],
}

def count_scholar_keywords(text):
    """
    Count the occurrences of keywords related to scholarly activities in the given text.
    """
    keyword_counts = {key: 0 for key in SCHOLAR_KEYWORDS}

    # Convert text to lowercase for case-insensitive matching
    lower_text = text.lower()

    # Iterate through each keyword category
    for keyword_category, keywords in SCHOLAR_KEYWORDS.items():
        for keyword in keywords:
            # Convert keyword to lowercase for case-insensitive matching
            lower_keyword = keyword.lower()

            # Count the occurrences of each keyword in the lowercased text
            keyword_counts[keyword_category] += lower_text.count(lower_keyword)

    return keyword_counts

def sanitize_filename(url):
    # Use regular expressions to replace invalid filename characters with underscores
    return re.sub(r'[\/:*?"<>|]', '_', url)

def fetch_content(url):
    try:
        with requests.Session() as session:
            response = session.get(url)
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

    # Use Bcc to hide the recipients' email addresses from each other
    message["Bcc"] = ", ".join(recipients)

    text = MIMEText(body, "plain")
    message.attach(text)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(os.environ["SMTP_SERVER"], os.environ["SMTP_PORT"], context=context) as server:
        server.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_PASSWORD"])
        
        # Note: The 'To' field is not set in the message to avoid disclosing email addresses
        server.sendmail(os.environ["EMAIL_ADDRESS"], recipients, message.as_string())

def send_invalid_url_email(recipients, url, status_code):
    subject = f"Website {url} is invalid or removed"
    body = f"The website {url} returned an HTTP status code {status_code}. Please check if the website is still valid or has been removed."
    send_email(recipients, subject, body)

def save_content(file_name, content):
    with open(file_name, 'wb') as f:
        pickle.dump(content, f)


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

def load_recipients_from_file(file_name):
    with open(file_name, 'r') as f:
        return [line.strip() for line in f]

def get_changed_text_context(old_text, new_text):
    """
    Compare old and new text and return changed text along with context.
    """
    # Tokenize text into words
    old_words = old_text.split()
    new_words = new_text.split()

    # Find differences using SequenceMatcher
    matcher = SequenceMatcher(None, old_words, new_words)
    opcodes = matcher.get_opcodes()

    # Extract changed text along with context
    changes = []
    current_change = {'old': [], 'new': []}

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'replace':
            old_change = ' '.join(old_words[i1:i2])
            new_change = ' '.join(new_words[j1:j2])
            current_change['old'].append(old_change)
            current_change['new'].append(new_change)
        elif tag == 'delete':
            old_change = ' '.join(old_words[i1:i2])
            current_change['old'].append(old_change)
        elif tag == 'insert':
            new_change = ' '.join(new_words[j1:j2])
            current_change['new'].append(new_change)

    if current_change['old'] or current_change['new']:
        changes.append(current_change)

    # Combine changes with entire sentences
    result = []
    for change in changes:
        if change['old'] or change['new']:
            old_sentence = ' '.join(change['old'])
            new_sentence = ' '.join(change['new'])
            result.append({'old': old_sentence, 'new': new_sentence})

    return result


def monitor_websites(websites, recipients):
            # Introduce a random sleep time between 1 and 3 seconds
    sleep_time = random.uniform(1, 3)
    time.sleep(sleep_time)

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
            # Count scholarly keywords in old and new content
            old_keyword_counts = count_scholar_keywords(old_content)
            new_keyword_counts = count_scholar_keywords(new_content)
            
            # If the word count difference is 3 or more, send an email with changed text and context
            if abs(new_word_count - old_word_count) >= 3:
                print(f"The website {url} has been updated.")
                
                # Get changed text and context
                changes = get_changed_text_context(old_content, new_content)

                # Build email body
                email_body = f"The website {url} has been updated.\n\n"
                for change in changes:
                    if change['old'] or change['new']:
                        email_body += f"Changed Text (Old): {change['old']}\n"
                        email_body += f"Changed Text (New): {change['new']}\n\n"
                email_body += "Paper status updates:\n"
                for category, count in old_keyword_counts.items():
                    email_body += f"{category.capitalize()}: {count} (Old) -> {new_keyword_counts[category]} (New)\n"
                
                # Send email
                send_email(
                    recipients,
                    f"Website update: {url}",
                    email_body
                )

                # Save the new content for future comparisons
                save_content(file_name, new_content)
                
if __name__ == "__main__":
    websites = load_urls_from_file("websites.txt")
    recipients = load_recipients_from_file("recipients.txt")

    monitor_websites(websites, recipients)