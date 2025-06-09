import os
import time
import logging
import threading
import json
import traceback
import subprocess
import send2trash

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import scrolledtext
from tkinter import ttk

# --- CONFIGURATION ---

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "SCREENSHOT_DIRECTORY": r"C:\\Users\\SOmeone\\Videos\\NVIDIA\\League of Legends",
    "USER_DATA_DIR": r"C:\\Users\\Someone\\AppData\\Local\\Google\\Chrome\\User Data",
    "PROFILE_DIRECTORY": "Default",
    "COUNTER_FILE": "post_counter.txt",
    "LOG_FILE": "program_log.txt",
    "DELAY_FB_TO_IG": 15,
    "DELAY_AFTER_IG": 60,
    "IG_COUNTER_KEY": "ig_counter",
    "FB_CAPTION_TEMPLATE": "Y{yo}, another fake win ra9m: {counter}",
    "IG_CAPTION_HASHTAGS": "#Gaming #VideoGames #GGWP #GamingMoments #GoodVibes"
}

# --- LAUNCH CHROME VIA BATCH FILE IF PRESENT ---
batch_file = os.path.abspath("launch_chrome_Version2.bat")
if os.path.isfile(batch_file):
    subprocess.Popen([batch_file], shell=True)

# --- LOAD CONFIG ---
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

config = load_config()
SCREENSHOT_DIRECTORY = config.get("SCREENSHOT_DIRECTORY", DEFAULT_CONFIG["SCREENSHOT_DIRECTORY"])
USER_DATA_DIR = config.get("USER_DATA_DIR", DEFAULT_CONFIG["USER_DATA_DIR"])
PROFILE_DIRECTORY = config.get("PROFILE_DIRECTORY", DEFAULT_CONFIG["PROFILE_DIRECTORY"])
COUNTER_FILE = config.get("COUNTER_FILE", DEFAULT_CONFIG["COUNTER_FILE"])
LOG_FILE = config.get("LOG_FILE", DEFAULT_CONFIG["LOG_FILE"])
DELAY_FB_TO_IG = config.get("DELAY_FB_TO_IG", DEFAULT_CONFIG["DELAY_FB_TO_IG"])
DELAY_AFTER_IG = config.get("DELAY_AFTER_IG", DEFAULT_CONFIG["DELAY_AFTER_IG"])
IG_COUNTER_KEY = config.get("IG_COUNTER_KEY", "ig_counter")
FB_CAPTION_TEMPLATE = config.get("fb_caption_template", DEFAULT_CONFIG["FB_CAPTION_TEMPLATE"])
IG_CAPTION_HASHTAGS = config.get("ig_caption_hashtags", DEFAULT_CONFIG["IG_CAPTION_HASHTAGS"])

# --- LOGGING ---
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# --- COUNTER UTILS ---

def get_post_counter():
    if not os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "w") as f:
            f.write("0")
    with open(COUNTER_FILE, "r") as f:
        return int(f.read().strip())

def increment_post_counter():
    count = get_post_counter() + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(count))
    return count

# Instagram counter uses config JSON!
def get_ig_counter():
    cfg = load_config()
    return int(cfg.get("ig_counter", 1))

def increment_ig_counter():
    cfg = load_config()
    count = int(cfg.get("ig_counter", 0)) + 1
    cfg["ig_counter"] = count
    save_config(cfg)
    return count

# --- CAPTION GENERATION ---

def generate_caption(template, counter):
    yo_text = "o" * counter
    return template.format(yo=yo_text, counter=counter)

class ScreenshotHandler(FileSystemEventHandler):
    def __init__(self, driver, log_callback):
        self.driver = driver
        self.log_callback = log_callback

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            self.log_callback(f"📸 New screenshot detected: {event.src_path}")
            threading.Thread(target=self.handle_uploads, args=(event.src_path,), daemon=True).start()

    def handle_uploads(self, screenshot_path):
        driver = self.driver
        try:
            # Facebook upload
            self.upload_to_facebook(screenshot_path)

            # Wait for user to see FB post
            self.log_callback(f"⏳ Waiting {DELAY_FB_TO_IG} seconds before opening Instagram...")
            time.sleep(DELAY_FB_TO_IG)

            # Save FB handle, then open Instagram in new tab
            fb_handle = driver.current_window_handle
            driver.execute_script("window.open('https://www.instagram.com/', '_blank');")
            ig_handle = driver.window_handles[-1]

            driver.switch_to.window(ig_handle)
            self.log_callback("🌈 Switched to Instagram tab.")

            # IG upload
            self.upload_to_instagram(screenshot_path)

            # Optionally, close the FB tab after IG upload
            try:
                if fb_handle in driver.window_handles:
                    driver.switch_to.window(fb_handle)
                    driver.close()
                    self.log_callback("❌ Closed Facebook tab after IG upload.")
            except Exception as e:
                self.log_callback(f"⚠️ Could not close Facebook tab: {e}")

            # Switch back to IG tab or remaining tab (if needed)
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])

        except Exception:
            error_message = f"❌ Failed to upload screenshot:\n{traceback.format_exc()}"
            logging.error(error_message)
            self.log_callback(error_message)

    def upload_to_facebook(self, screenshot_path):
        driver = self.driver
        try:
            self.log_callback("🔎 Searching for existing Facebook tab...")
            found_fb_tab = False
            for handle in driver.window_handles:
                driver.switch_to.window(handle)
                if "facebook.com" in driver.current_url:
                    self.log_callback(f"🔄 Switched to existing Facebook tab: {driver.current_url}")
                    found_fb_tab = True
                    break

            if not found_fb_tab:
                self.log_callback("🌍 No existing Facebook tab found. Navigating to Facebook...")
                driver.get("https://www.facebook.com/")

            wait = WebDriverWait(driver, 30)
            self.log_callback("⏳ Waiting for post initiation button...")
            post_button = wait.until(EC.element_to_be_clickable((By.XPATH,
                '//div[@role="button"]//span[contains(text(), "What\'s on your mind")]/ancestor::div[@role="button"]')))
            post_button.click()

            self.log_callback("💬 Waiting for post text box to load...")
            text_area = wait.until(EC.presence_of_element_located((By.XPATH,
                '//div[contains(@aria-placeholder, "What\'s on your mind")]')))

            self.log_callback("🖼️ Waiting for Photo/video section...")
            media_section = wait.until(EC.element_to_be_clickable((By.XPATH,
                '//div[@aria-label="Photo/video"]')))
            media_section.click()

            self.log_callback("📂 Waiting for file input to appear...")
            file_input = wait.until(EC.presence_of_element_located((By.XPATH,
                '//input[@type="file" and contains(@accept, "image/*")]')))
            file_input.send_keys(screenshot_path)

            self.log_callback("✍️ Writing caption...")
            post_number = increment_post_counter()
            caption = generate_caption(FB_CAPTION_TEMPLATE, post_number)
            text_area.send_keys(caption)

            self.log_callback("⏳ Waiting for Post button...")
            # --- DO NOT POST --- (commented as requested)
            # post_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//div[@role="button" and @aria-label="Post"]')))
            # post_btn.click()

            time.sleep(5)
            success_message = f"✅ Screenshot posted successfully (not really, post click commented): {screenshot_path}"
            logging.info(success_message)
            self.log_callback(success_message)
        except Exception:
            error_message = f"❌ Failed to upload screenshot to Facebook:\n{traceback.format_exc()}"
            logging.error(error_message)
            self.log_callback(error_message)

    def upload_to_instagram(self, image_path):
        try:
            driver = self.driver
            wait = WebDriverWait(driver, 30)

            self.log_callback("⏳ Waiting for 'Create' button...")
            create_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//a[@role="link"][.//span[text()="Create"]]'))
            )
            create_btn.click()
            self.log_callback("✅ Clicked 'Create'.")

            self.log_callback("⏳ Waiting for 'Post' option...")
            post_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//a[@role="link"][.//span[text()="Post"]]'))
            )
            post_btn.click()
            self.log_callback("✅ Clicked 'Post'.")

            self.log_callback("⏳ Waiting for 'Select from computer' button...")
            select_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[normalize-space(text())="Select from computer"]'))
            )
            select_btn.click()
            self.log_callback("✅ Clicked 'Select from computer'.")

            self.log_callback("⏳ Waiting for file input to appear...")
            file_input = wait.until(
                EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
            )
            file_input.send_keys(image_path)
            self.log_callback(f"🖼️ Image selected for upload: {image_path}")

            self.log_callback("⏳ Waiting for first 'Next' button...")
            next_btn1 = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//div[@role="button" and text()="Next"]'))
            )
            next_btn1.click()
            self.log_callback("✅ Clicked first 'Next'.")

            self.log_callback("⏳ Waiting for second 'Next' button...")
            next_btn2 = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//div[@role="button" and text()="Next"]'))
            )
            next_btn2.click()
            self.log_callback("✅ Clicked second 'Next'.")

            self.log_callback("⏳ Waiting for caption box...")
            tries = 0
            while tries < 3:
                try:
                    caption_box = wait.until(
                        EC.visibility_of_element_located((
                            By.XPATH, '//div[@aria-label="Write a caption..." and @role="textbox" and @contenteditable="true"]'
                        ))
                    )
                    caption_box.click()
                    ig_post_number = increment_ig_counter()
                    caption = generate_caption(FB_CAPTION_TEMPLATE, ig_post_number)
                    full_caption = f"{caption} {IG_CAPTION_HASHTAGS}".strip()
                    caption_box.send_keys(full_caption)
                    self.log_callback("✅ Caption entered.")
                    break
                except StaleElementReferenceException:
                    self.log_callback("[IG] Caption box went stale, retrying...")
                    tries += 1
                    time.sleep(1)
            else:
                self.log_callback("[IG] Failed to enter caption after 3 tries.")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                return

            self.log_callback("⏳ Waiting for 'Share' button...")
            # --- DO NOT SHARE --- (commented)
            # share_btn = wait.until(
            #     EC.element_to_be_clickable((By.XPATH, '//div[@role="button" and text()="Share"]'))
            # )
            # share_btn.click()
            self.log_callback("🚦 Share button is ready (click is commented out).")

            try:
                send2trash.send2trash(os.path.normpath(image_path))
                self.log_callback(f"🗑️ Sent screenshot to Recycle Bin: {image_path}")
                logging.info(f"Sent screenshot to Recycle Bin: {image_path}")
            except Exception as delete_error:
                logging.warning(f"Failed to send screenshot to Recycle Bin: {delete_error}")
                self.log_callback(f"⚠️ Failed to send screenshot to Recycle Bin: {delete_error}")
            self.log_callback(f"✅ Instagram (simulated) upload complete. Waiting {DELAY_AFTER_IG}s before closing IG tab.")
            time.sleep(DELAY_AFTER_IG)
            # IG tab will be closed by handle_uploads

        except Exception:
            error_message = f"❌ Failed Instagram upload:\n{traceback.format_exc()}"
            logging.error(error_message)
            self.log_callback(error_message)

# --- GUI APP CLASS ---

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("📷 Facebook & Instagram Auto-Uploader")
        self.root.geometry("780x560")
        self.root.resizable(False, False)
        self.stop_event = threading.Event()

        # Colors
        FB_BLUE = "#1877F2"
        LIGHTER_BLUE = "#1C8EF9"
        DARKER_BLUE = "#0e5cbf"
        WHITE = "#FFFFFF"
        BLACK = "#202124"
        GREEN = "#28a745"
        RED = "#dc3545"

        self.root.configure(bg=FB_BLUE)
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=FB_BLUE)
        self.style.configure("TButton", background=LIGHTER_BLUE, foreground=WHITE, font=("Segoe UI", 11, "bold"))
        self.style.map("TButton", background=[('active', DARKER_BLUE)])

        # Frame for main controls
        self.frame = ttk.Frame(root, padding=20, style="TFrame")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(self.frame, text="🎯 Facebook & Instagram Auto-Uploader", font=("Segoe UI", 19, "bold"),
                               bg=FB_BLUE, fg=WHITE)
        title_label.pack(pady=(0, 10))

        # Directory info
        dir_frame = tk.Frame(self.frame, bg=FB_BLUE)
        dir_frame.pack(pady=(0, 10), fill=tk.X)
        tk.Label(dir_frame, text="Screenshot Directory:", bg=FB_BLUE, fg=WHITE, font=("Segoe UI", 11)).pack(side=tk.LEFT)
        self.dir_entry = tk.Entry(dir_frame, width=50, font=("Segoe UI", 10))
        self.dir_entry.insert(0, SCREENSHOT_DIRECTORY)
        self.dir_entry.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(dir_frame, text="Browse", command=self.browse_folder).pack(side=tk.LEFT, padx=(8, 0))

        # Control buttons
        btn_frame = tk.Frame(self.frame, bg=FB_BLUE)
        btn_frame.pack(pady=(0, 15), fill=tk.X)
        self.start_button = ttk.Button(btn_frame, text="▶️ Start Watching", command=self.start_program)
        self.start_button.pack(side=tk.LEFT, padx=7, fill=tk.X, expand=True)
        self.stop_button = ttk.Button(btn_frame, text="⏹️ Stop", command=self.stop_program, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=7, fill=tk.X, expand=True)
        self.ig_test_button = ttk.Button(btn_frame, text="🧪 Test IG Upload", command=self.test_ig_upload)
        self.ig_test_button.pack(side=tk.LEFT, padx=7, fill=tk.X, expand=True)

        # Log Viewer
        self.log_viewer = scrolledtext.ScrolledText(
            self.frame,
            width=90,
            height=22,
            wrap=tk.WORD,
            bg=BLACK,
            fg=WHITE,
            insertbackground=WHITE,
            font=("Consolas", 10)
        )
        self.log_viewer.pack(fill=tk.BOTH, expand=True, pady=8)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready.")
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                  bg=DARKER_BLUE, fg=WHITE, font=("Segoe UI", 10))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, msg):
        self.status_var.set(msg)

    def log_message(self, message):
        self.log_viewer.insert(tk.END, f"{message}\n")
        self.log_viewer.see(tk.END)
        self.set_status(message if len(message) < 120 else message[:120]+"...")

    def browse_folder(self):
        folder_selected = filedialog.askdirectory(
            title="Select Screenshot Directory",
            initialdir=self.dir_entry.get() if os.path.exists(self.dir_entry.get()) else os.getcwd()
        )
        if folder_selected:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, folder_selected)
            global SCREENSHOT_DIRECTORY
            SCREENSHOT_DIRECTORY = folder_selected
            self.log_message(f"📁 Screenshot directory set to: {folder_selected}")

    def start_program(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.ig_test_button.config(state=tk.DISABLED)
        self.stop_event.clear()
        self.log_message("🚦 Starting program...")
        threading.Thread(target=self.run_program, daemon=True).start()

    def stop_program(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.ig_test_button.config(state=tk.NORMAL)
        self.stop_event.set()
        if hasattr(self, 'observer'):
            try:
                self.observer.stop()
                self.observer.join()
            except Exception:
                pass
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except Exception:
                pass
        logging.info("Program stopped.")
        self.log_message("⛔ Program stopped.")
        self.set_status("Stopped.")

    def run_program(self):
        try:
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=chrome_options)
            logging.info("WebDriver attached to existing Chrome instance.")
            self.log_message("🟢 WebDriver attached to existing Chrome instance.")

            self.keep_alive_thread = threading.Thread(target=self.keep_alive, daemon=True)
            self.keep_alive_thread.start()
            logging.info("Keep-alive thread started.")

            event_handler = ScreenshotHandler(self.driver, self.log_message)
            self.observer = Observer()
            self.observer.schedule(event_handler, SCREENSHOT_DIRECTORY, recursive=False)
            self.observer.start()
            self.log_message(f"👀 Watching directory: {SCREENSHOT_DIRECTORY}")

            while not self.stop_event.is_set():
                time.sleep(1)

        except Exception as e:
            error_message = f"❌ Error: {str(e)}"
            logging.error(error_message)
            self.log_message(error_message)
            self.set_status("Error. See log.")
        finally:
            try:
                if hasattr(self, 'observer'):
                    self.observer.stop()
                    self.observer.join()
                if hasattr(self, 'driver'):
                    self.driver.quit()
            except Exception:
                pass

    def keep_alive(self):
        while not self.stop_event.is_set():
            try:
                self.driver.execute_script("return document.title;")
                time.sleep(30)
            except Exception as e:
                logging.error(f"Keep-alive failed: {e}")
                break

    def test_ig_upload(self):
        image_path = filedialog.askopenfilename(
            title="Select an image for Instagram upload test",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")]
        )
        if image_path:
            try:
                chrome_options = Options()
                chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                driver = webdriver.Chrome(options=chrome_options)
                handler = ScreenshotHandler(driver, self.log_message)
                handler.upload_to_instagram(image_path)
                driver.quit()
                self.log_message("✅ IG upload test finished.")
            except Exception as e:
                self.log_message(f"❌ IG Test error: {e}")

# --- MAIN ---

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()