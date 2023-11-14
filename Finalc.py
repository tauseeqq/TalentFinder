from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pandas as pd
import os
import time
import instaloader
import sqlite3
import random

global instagram_username
global instagram_password
CSV_PATH = 'data_1.csv'
instagram_username = '106recordsofficial'
instagram_password = 'Pakistanzindabad12345'

def load_session(L, username, password):
    try:
        L.load_session_from_file(username)
    except FileNotFoundError:
        # If the session file does not exist, login and create a session file
        L.login(username, password)
        L.save_session_to_file(username)
        
def random_delay(min_delay=2, max_delay=5):
    """Wait for a random time between `min_delay` and `max_delay` seconds."""
    time.sleep(random.uniform(min_delay, max_delay))

def handle_2fa(page):
    """Handles two-factor authentication if prompted."""
    two_factor_code = input("Enter the two-factor authentication code: ")
    page.fill("input[name='verificationCode']", two_factor_code)
    page.click("button[type='submit']")
    random_delay(5, 10)  # Random delay to mimic user waiting for 2FA to process

def login_to_instagram(page, username, password):
    print("Logging in to Instagram...")
    page.goto('https://www.instagram.com/accounts/login/')
    page.wait_for_selector("input[name='username']", state="visible")
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    random_delay(5, 10)  # Random delay to wait for login to complete
    # Check if 2FA is required
    if page.is_visible("input[name='verificationCode']"):
        handle_2fa(page)

def navigate_to_reels(page):
    """Navigates to the Instagram Reels page."""
    print("Navigating to Reels...")
    page.goto('https://www.instagram.com/reels/')
    page.wait_for_load_state('networkidle')
    print("Navigated to Reels.")


def scroll_to_next_reel(page):
    """Scrolls down to the next Instagram Reel."""
    print("Scrolling to the next Reel...")
    page.mouse.wheel(0, random.randint(300, 700))  # Random scroll distance
    random_delay(1, 3)  # Random delay after scroll
    print("Scrolled to the next Reel.")


def click_more_options_and_embed(page):
    """Clicks 'More Options', 'Embed', extracts the embed code, and extracts the username."""
    print("Clicking 'More Options' button...")
    retries = 3  # Number of retries
    retry_delay = 2  # Delay between retries in seconds
    username = None  # Initialize username to None

    for attempt in range(retries):
        more_options_button = page.query_selector('svg[aria-label="More"]')
        if more_options_button:
            more_options_button.click()
            print("Clicked 'More Options' button.")
            page.wait_for_timeout(2000)

            # Click 'Embed' and extract the embed code
            embed_button = page.query_selector('text=Embed')
            if embed_button:
                embed_button.click()
                print("Clicked 'Embed'.")
                page.wait_for_timeout(2000)
                
                # Locate the embed code textarea and extract the username
                embed_code_textarea = page.query_selector("textarea")
                if embed_code_textarea:
                    embed_code = embed_code_textarea.input_value()
                    print("Embed code extracted.")
                    username = extract_username_from_embed_code(embed_code)
                    if username:
                        print("Username extracted:", username)
                        return username  # If username is found, return it immediately
                    else:
                        print("Username could not be extracted.")
                else:
                    print("Embed code textarea not found.")
            else:
                print("'Embed' option not found.")
            break  # Break the loop if 'More Options' was found, even if no username was extracted
        else:
            print(f"'More Options' button not found, retrying... (Attempt {attempt + 1} of {retries})")
            page.wait_for_timeout(retry_delay * 1000)  # Wait before retrying
            scroll_to_next_reel(page)  # Scroll a bit to check if it triggers the button to appear

    print("Finished attempts to find 'More Options' button.")
    return username  # Return username, which will be None if not found

def extract_username_from_embed_code(embed_code):
    """Extracts the Instagram username from the embed code."""
    soup = BeautifulSoup(embed_code, "html.parser")
    a_tag = soup.find("a", string=lambda text: "A post shared by" in text if text else False)
    if not a_tag:
        return None
    text_content = a_tag.get_text(strip=True)
    username = text_content.split('@')[-1].split(')')[0].strip()
    return username

def save_username_to_csv(username, followers_count, engagement, csv_path):
    """Saves the Instagram username, follower count, and engagement to a CSV file."""
    new_row = pd.DataFrame({
        'username': [username],
        'followers_count': [followers_count],
        'engagement': [engagement]
    })
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        df = new_row
    df.to_csv(csv_path, index=False)
    print(f"Username, followers, and engagement saved to {csv_path}")

def check_login_status(page):
    # Check if login fields are present which indicates we are logged out
    if page.is_visible("input[name='username']"):
        print("Not logged in. Attempting to log back in...")
        login_to_instagram(page, instagram_username, instagram_password)

def close_options_modal(page):
    """Closes the 'More Options' modal by clicking outside it twice."""
    print("Closing 'More Options' modal...")
    
    # Click outside the modal twice to close it
    page.mouse.click(10, 10)  # Click outside the modal (first click)
    page.wait_for_timeout(1000)
    
    page.mouse.click(10, 10)  # Click outside the modal again (second click)
    page.wait_for_timeout(1000)
    
    print("Closed 'More Options' modal.")
    
def parse_followers_count(followers_text):
    """Parse the followers count text to an integer."""
    followers_text = followers_text.lower().replace(',', '')
    multiplier = 1

    if 'k' in followers_text:
        multiplier = 1000
        followers_text = followers_text.replace('k', '')
    elif 'm' in followers_text:
        multiplier = 1000000
        followers_text = followers_text.replace('m', '')

    # For counts like '1,234' after removing 'k' or 'm'
    if '.' in followers_text:
        parts = followers_text.split('.')
        main_part = parts[0]
        decimal_part = parts[1]
        # Adjust the multiplier based on the number of decimal places
        multiplier /= 10 ** len(decimal_part)
        followers_text = main_part + decimal_part

    return int(float(followers_text) * multiplier)

def get_followers_count(page, username):
    """Gets the number of followers for a given username."""
    profile_url = f'https://www.instagram.com/{username}/'
    page.goto(profile_url)
    page.wait_for_selector('header section ul li a span', state='visible')  # Adjust the selector based on the current Instagram layout
    followers_element = page.query_selector('header section ul li a span')
    followers_count_text = followers_element.inner_text()

    # Use the helper function to parse the text to an integer
    followers_count = parse_followers_count(followers_count_text)
    return followers_count

def get_total_likes_of_last_reels(L, username, max_reels=10):
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        posts = profile.get_posts()

        total_likes = 0
        count = 0

        for post in posts:
            if post.is_video and count < max_reels:
                total_likes += post.likes
                count += 1
            if count == max_reels:
                break

        return total_likes
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"The profile {username} does not exist.")
        return None
    except Exception as e:
        print(f"An error occurred when getting total likes: {e}")
        return None

def get_total_comments_of_last_reels(L, username, max_reels=10):
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        posts = profile.get_posts()

        total_comments = 0
        count = 0

        for post in posts:
            if post.is_video and count < max_reels:
                total_comments += post.comments
                count += 1
            if count == max_reels:
                break

        return total_comments
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"The profile {username} does not exist.")
        return None
    except Exception as e:
        print(f"An error occurred when getting total comments: {e}")
        return None

def get_total_views_of_last_reels(L, username, max_reels=10):
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        posts = profile.get_posts()

        total_views = 0
        count = 0

        for post in posts:
            if post.is_video and count < max_reels:
                total_views += post.video_view_count
                count += 1
            if count == max_reels:
                break

        return total_views
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"The profile {username} does not exist.")
        return None
    except Exception as e:
        print(f"An error occurred when getting total views: {e}")
        return None

def calculate_engagement(total_likes, total_comments, total_views):
    """Calculates the engagement rate."""
    if total_views == 0:  # Prevent division by zero
        return 0
    return (total_likes + total_comments) / total_views
def main():
    """Main function to run the Instagram scraper."""
    if not instagram_username or not instagram_password:
        raise ValueError("Instagram credentials are not set.")

    L = instaloader.Instaloader()
    load_session(L, instagram_username, instagram_password)  # Load or create a session

    with sync_playwright() as p:
        browser = p.webkit.launch(headless=False)  # Set headless=False to see the browser window
        page = browser.new_page()
        login_to_instagram(page, instagram_username, instagram_password)

        # Check for two-factor authentication (2FA) if needed
        if page.is_visible("input[name='verificationCode']"):
            handle_2fa(page)

        num_users_logged = 0
        max_users_to_log = 5  # Set to the desired number of users to log

        try:
            while num_users_logged < max_users_to_log:
                navigate_to_reels(page)
                username = click_more_options_and_embed(page)
                if username:
                    followers_count = get_followers_count(page, username)
                    if followers_count < 10000:  # Store only if followers count is less than 10k
                        total_likes = get_total_likes_of_last_reels(L, username)
                        total_comments = get_total_comments_of_last_reels(L, username)
                        total_views = get_total_views_of_last_reels(L, username)

                        if total_likes is not None and total_comments is not None and total_views is not None:
                            engagement = calculate_engagement(total_likes, total_comments, total_views)
                            save_username_to_csv(username, followers_count, engagement, CSV_PATH)
                            print(f"Stored {username} with {followers_count} followers and an engagement of {engagement}.")
                            num_users_logged += 1
                            check_login_status(page)  # Check if still logged in after storing the entry
                        else:
                            print(f"Could not retrieve data for {username}.")
                    else:
                        print(f"Skipped {username} with {followers_count} followers (10k or more).")
                    close_options_modal(page)
                else:
                    close_options_modal(page)
                scroll_to_next_reel(page)

        except Exception as e:
            print(f"An error occurred: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    main()