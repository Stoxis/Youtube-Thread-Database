import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Progressbar
import tkinter.font as tkFont
import json
import re
import math
import time
import threading
import traceback
import html
from PIL import Image, ImageTk
import requests
from io import BytesIO
import webbrowser
import APIpostgres

# TODO: Test what happens if no settings file exists and fix any issues
# TODO: create a system to check threads automatically after a specific amount of time since it was last checked and notify you of any deletions or direct replies, or any specific keywords

SETTINGS_FILE = "settings.json"

def copy_selected_text(event):
    widget = event.widget
    if isinstance(widget, tk.Entry):
        if widget.selection_present():
            selected_text = widget.selection_get()
            if selected_text:
                widget.clipboard_clear()
                widget.clipboard_append(selected_text)
    elif isinstance(widget, tk.Text):
        if widget.tag_ranges("sel"):
            selected_text = widget.get("sel.first", "sel.last")
            if selected_text:
                widget.clipboard_clear()
                widget.clipboard_append(selected_text)

def select_all_text(event):
    widget = event.widget
    if isinstance(widget, tk.Entry):
        widget.select_range(0, tk.END)
        widget.icursor(tk.END)
    elif isinstance(widget, tk.Text):
        widget.tag_add("sel", "1.0", "end")
    return "break"  # Prevent the default behavior of Ctrl+A


# List of common fonts to be used, ordered by priority
common_fonts = ["Helvetica", "Arial", "Verdana", "Tahoma", "Times New Roman", "Courier New", "Georgia"]

# Function to open the comment visualizer window
def open_comment_visualizer(comments): # Make posted date link to actual comment
    comment_window = tk.Toplevel(root)
    comment_window.title("Comment Visualizer")
    
    visualization_loaded = False
    
    def check_and_destroy_window():
        if not visualization_loaded:
            print("Hiding visualizer window")
            comment_window.withdraw()
        while not visualization_loaded:
            # Check if the visualization is loaded, if not, wait for a short period
            time.sleep(10)

        # Destroy the window once the visualization is loaded
        print("removing visualizer window")
        comment_window.destroy() 
    
    def close_visualizer_window():
        # Start a separate thread to check and destroy the window
        thread = threading.Thread(target=check_and_destroy_window)
        thread.start()

    # Function to destroy the comment window and cleanup resources
    comment_window.protocol("WM_DELETE_WINDOW", close_visualizer_window)

    # Create a Canvas widget for scrolling
    canvas = tk.Canvas(comment_window)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Set the initial size of the window
    comment_window.geometry("485x600")

    # Create a vertical scrollbar
    scrollbar = tk.Scrollbar(comment_window, command=canvas.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Configure the Canvas to use the scrollbar for scrolling
    canvas.configure(yscrollcommand=scrollbar.set)

    # Create a frame inside the Canvas to hold the comments
    frame = tk.Frame(canvas)
    canvas.create_window((0, 0), window=frame, anchor="nw")

    # Function to create a divider line between comments
    def create_divider():
        divider = tk.Frame(frame, height=2, bd=1, relief=tk.SUNKEN)
        return divider

    def find_font(font_list):
        for font in font_list:
            if font in tkFont.names():
                return font
        return "Helvetica"  # Fallback to a default font if none of the fonts in the list are available

    # Function to create a font style using the available common fonts or a default font
    def create_font(family, size, weight):
        available_font = find_font([family] + common_fonts)
        return tkFont.Font(family=available_font, size=size, weight=weight)

    def configure_canvas(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    # Wait for the window to be fully created before configuring the canvas
    comment_window.bind("<Map>", configure_canvas)

    for i, comment in enumerate(comments):
        username = comment.get("Username", "")
        comment_text = html.unescape(comment.get("Comment", "")).replace("<br>", "\n")

        profile_picture_url = comment.get("ProfilePictureURL", "")
        post_date = comment.get("PostDate", "")
        likes = comment.get("Likes", 0)
        is_deleted = comment.get("Deleted", False)

        response = requests.get(profile_picture_url)
        image = Image.open(BytesIO(response.content))
        image = image.resize((48, 48))
        photo = ImageTk.PhotoImage(image)

        profile_picture_label = tk.Label(frame, image=photo)
        profile_picture_label.image = photo
        profile_picture_label.grid(row=i * 3, column=0, padx=5, pady=(30, 0), rowspan=3, sticky="nw")

        # Function to handle clicking the username label
        def open_channel(event):
            webbrowser.open(f"https://www.youtube.com/channel/{comment['ChannelID']}")

        if comment['ChannelID']:
            # If there is a ChannelID, make the username label clickable
            username_label = tk.Label(frame, text=username, foreground="blue", cursor="hand2",
                                      font=create_font("Arial", 12, "bold"))
            username_label.grid(row=i * 3 + 1, column=1, padx=5, pady=0, columnspan=2, sticky="w")
            username_label.bind("<Button-1>", open_channel)
        else:
            # If there is no ChannelID, just display the username as plain text
            username_label = tk.Label(frame, text=username, font=create_font("Arial", 12, "bold"))
            username_label.grid(row=i * 3 + 1, column=1, padx=5, pady=0, columnspan=2, sticky="w")

        post_date_label = tk.Label(frame, text=f"Posted on: {post_date}", font=create_font("Arial", 10, "normal"))
        post_date_label.grid(row=i * 3 + 1, column=2, padx=(5, 0), pady=(0, 0), columnspan=1, sticky="w")

        if is_deleted:
            comment_text = f"[Deleted] {comment_text}"
            comment_label = tk.Label(frame, text=comment_text, foreground="red", wraplength=400, anchor="w",
                                     justify="left", font=create_font("Arial", 12, "normal"))
        else:
            comment_label = tk.Label(frame, text=comment_text, wraplength=400, anchor="w", justify="left",
                                     font=create_font("Arial", 12, "normal"))

        comment_label.grid(row=i * 3 + 2, column=1, padx=5, pady=(0, 0), columnspan=4, sticky="nw")

        likes_label = tk.Label(frame, text=f"Likes: {likes}", font=create_font("Arial", 10, "normal"))
        likes_label.grid(row=i * 3 + 3, column=1, padx=5, pady=(0, 0), sticky="w")

        # Create a divider line between comments
        divider = create_divider()
        divider.grid(row=i * 3 + 4, column=0, columnspan=5, padx=5, pady=(0, 40), sticky="ew")

    # Set a flag to indicate that the visualization is loaded
    visualization_loaded = True
    print("visualization loaded")

# Define the main window
root = tk.Tk()
root.title("API and Database Settings")

# Load settings from file or create default settings
try:
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {
        "api_key": "",
        "db_name": "",
        "db_user": "",
        "db_pass": "",
        "db_url": "",
        "wait_time": "",
        "max-results": "",
        "enable_cache": True
    }

# Save settings to file
def save_settings():
    settings["api_key"] = api_key_entry.get()
    settings["db_name"] = db_name_entry.get()
    settings["db_user"] = db_user_entry.get()
    settings["db_pass"] = db_pass_entry.get()
    settings["db_url"] = db_url_entry.get()
    settings["wait_time"] = wait_entry.get()
    settings["max-results"] = result_entry.get()
    settings["enable_cache"] = enable_cache_var.get()

    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)
    
    APIpostgres.initiate_db()
    
# Update output text
def update_output(text):
    output_text.insert("end", f"{text}\n")# Generate Network@HTML Option
    
    # Scroll the output box to the bottom
    output_text.see("end")

# Clear output text
def clear_output():
    output_text.delete("1.0", "end")

# Update progress bar value
def update_progressbar(value):
    progress_bar["value"] = value

# Get values from input fields
def get_input_values():
    values = {
        "api_key": api_key_entry.get(),
        "db_name": db_name_entry.get(),
        "db_user": db_user_entry.get(),
        "db_pass": db_pass_entry.get(),
        "db_url": db_url_entry.get(),
        "wait_time": wait_entry.get(),
        "max-results": result_entry.get(),
        "enable_cache": enable_cache_var.get(),
        "search_query": search_entry.get(),
        "search_type": search_type_var.get(),
        "urls": input_text.get("1.0", "end").strip().split("\n")
    }
    return values

def extract_comment_ids(urls):
    comment_ids = []

    for url in urls:
        match = re.search(r"(?<=lc=)[\w-]+", url)
        if match:
            comment_id = match.group()
            if comment_id not in comment_ids:
                comment_ids.append(comment_id)
        else:
            # If the URL does not contain a comment ID, assume it is a direct comment ID
            if url not in comment_ids:
                comment_ids.append(url)

    return comment_ids

def create_array_from_string(string):
    array = re.split(r',\s*|,', string)
    return array

# DB Adder Option
def add_to_database_background():
    thread = threading.Thread(target=add_to_database)
    thread.start()

def add_to_database(): #TODO: Add error handling for invalid or deleted thread IDs that don't exist in the API or in the database
    update_progressbar(0)
    currentSettings = get_input_values()
    # Retrieve the URLs from the input box and process them
    urls = currentSettings["urls"]
    
    threads = extract_comment_ids(urls)
    
    progressStep = 100/len(threads)
    while threads:
        update_progressbar(progress_bar["value"] + progressStep)
        thread = threads.pop(0)  # Get the first API string from the array and remove it
        print(thread)
        api_response = APIpostgres.api_retrieve_thread(thread, update_output, clear_output, update_progressbar, get_input_values)
        json_object = json.dumps(api_response, indent=4)
        with open('api.json', 'w') as f:
            f.write(json_object)
        if "items" in api_response and len(api_response["items"]) > 0:  # If toplevel comment isn't deleted
            comments = APIpostgres.process_and_save_data(api_response, update_output, clear_output, update_progressbar, get_input_values)
        else:
            update_output(f"Current ThreadID returned empty response: {thread}")
        if threads:  # Check if it's the last value in the loop
            try:
                string_int = int(currentSettings["wait_time"])
                time.sleep(string_int)
            except ValueError:
                # Handle the exception
                time.sleep(2)

# Generate Network@HTML Option
def generate_network_html():
    APIpostgres.create_vis_network(update_output, clear_output, update_progressbar, get_input_values)
    update_output("Network generated")
    # Perform the network generation and get the file location
    #file_location = "/path/to/generated/network.html"
    #messagebox.showinfo("Success", f"Network generated successfully.\nFile Location: {file_location}")

# Comment visualizer option
def view_comment_thread_background():
    thread = threading.Thread(target=view_comment_thread)
    thread.start()

def view_comment_thread():
    thread = APIpostgres.get_thread_by_id(thread_id_entry.get())
    if thread:
        for comment in thread:
            # add this profile picture url along 
            comment["ProfilePictureURL"] = APIpostgres.get_profile_picture_url(comment["ChannelID"])
        
        # Open the comment visualizer window
        open_comment_visualizer(thread)
    else:
        # The thread_id is not valid, display an error message or handle it as needed
        print("Thread ID not found in the database.")


# Check DB Option
def check_database_background():
    thread = threading.Thread(target=check_database)
    thread.start()

def check_database():
    try:
        currentSettings = get_input_values()
        # Retrieve the search query from the input box
        search_query = search_entry.get()
        # Retrieve the blacklist from the input box
        blacklist = blacklist_entry.get()
        # Retrieve the search type from the dropdown selector
        search_type = search_type_var.get()

        # Perform database search and display results in the output box
        matching = APIpostgres.search_db(search_query, create_array_from_string(blacklist), search_type, currentSettings["max-results"])
        if search_type == "user":
            update_output(f"Results for search query ({search_type}) @ {search_query}: {matching}")
        elif search_type == "thread":
            update_output(f"Results for search query ({search_type}) @ {search_query}: {matching}")
        elif search_type == "comment":
            if matching:
                for comment in matching:
                    comment["ProfilePictureURL"] = APIpostgres.get_profile_picture_url(comment["ChannelID"])
                open_comment_visualizer(matching)
                update_output(f"Results for search query ({search_type}) @ {search_query}:")
                for comment in matching:
                    username = html.unescape(comment.get("Username", ""))
                    comment_text = html.unescape(comment.get("Comment", "")).replace("<br>", "\n")
                    comment_id = html.unescape(comment.get("CommentID", ""))
                    #output = f"({comment_id}) {username}: {comment_text}\n"
                    output = f"{username}:\n{comment_text}\n"
                    update_output(output)
    except Exception as e:
        traceback_info = traceback.format_exc()
        update_output(f"An error occurred: {e}\n{traceback_info}")


# Toggle visibility of settings frame
def toggle_settings():
    if settings_frame.winfo_ismapped():
        settings_frame.grid_forget()
        toggle_button.configure(text="Show Settings")
    else:
        settings_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        toggle_button.configure(text="Hide Settings")

# Toggle button for settings
toggle_button = tk.Button(root, text="Show Settings", command=toggle_settings)
toggle_button.grid(row=0, column=0, pady=10)

# Settings Frame
settings_frame = tk.LabelFrame(root, text="Settings")

# API Key Settings
api_key_label = tk.Label(settings_frame, text="API Key:")
api_key_label.grid(row=0, column=0, sticky="w")

api_key_entry = tk.Entry(settings_frame)
api_key_entry.grid(row=0, column=1, pady=5)
api_key_entry.insert(0, settings["api_key"])
api_key_entry.bind("<Control-c>", copy_selected_text)
api_key_entry.bind("<Control-a>", select_all_text)

# Database Settings
db_name_label = tk.Label(settings_frame, text="DB Name:")
db_name_label.grid(row=1, column=0, sticky="w")
db_name_entry = tk.Entry(settings_frame)
db_name_entry.grid(row=1, column=1, pady=5)
db_name_entry.insert(0, settings["db_name"])
db_name_entry.bind("<Control-c>", copy_selected_text)
db_name_entry.bind("<Control-a>", select_all_text)

db_user_label = tk.Label(settings_frame, text="DB Username:")
db_user_label.grid(row=2, column=0, sticky="w")
db_user_entry = tk.Entry(settings_frame)
db_user_entry.grid(row=2, column=1, pady=5)
db_user_entry.insert(0, settings["db_user"])
db_user_entry.bind("<Control-c>", copy_selected_text)
db_user_entry.bind("<Control-a>", select_all_text)

db_pass_label = tk.Label(settings_frame, text="DB Password:")
db_pass_label.grid(row=3, column=0, sticky="w")
db_pass_entry = tk.Entry(settings_frame, show="*")
db_pass_entry.grid(row=3, column=1, pady=5)
db_pass_entry.insert(0, settings["db_pass"])
db_pass_entry.bind("<Control-c>", copy_selected_text)
db_pass_entry.bind("<Control-a>", select_all_text)

db_url_label = tk.Label(settings_frame, text="DB URL:")
db_url_label.grid(row=4, column=0, sticky="w")
db_url_entry = tk.Entry(settings_frame)
db_url_entry.grid(row=4, column=1, pady=5)
db_url_entry.insert(0, settings["db_url"])
db_url_entry.bind("<Control-c>", copy_selected_text)
db_url_entry.bind("<Control-a>", select_all_text)

# Wait Time Settings
wait_label = tk.Label(settings_frame, text="Wait Time (seconds):")
wait_label.grid(row=5, column=0, sticky="w")

wait_entry = tk.Entry(settings_frame)
wait_entry.grid(row=5, column=1, pady=5)
wait_entry.insert(0, settings["wait_time"])
wait_entry.bind("<Control-c>", copy_selected_text)
wait_entry.bind("<Control-a>", select_all_text)

# Wait Time Settings
result_label = tk.Label(settings_frame, text="Search results (comments):")
result_label.grid(row=6, column=0, sticky="w")

result_entry = tk.Entry(settings_frame)
result_entry.grid(row=6, column=1, pady=5)
result_entry.insert(0, settings["max-results"])
result_entry.bind("<Control-c>", copy_selected_text)
result_entry.bind("<Control-a>", select_all_text)

# Enable Cache Settings
enable_cache_var = tk.BooleanVar()
enable_cache_var.set(settings["enable_cache"])  # Set the initial value based on settings

enable_cache_checkbtn = tk.Checkbutton(settings_frame, text="Enable downloading profile pictures locally?", variable=enable_cache_var)
enable_cache_checkbtn.grid(row=7, columnspan=2, pady=5)

# Save button
save_button = tk.Button(settings_frame, text="Save Settings", command=save_settings)
save_button.grid(row=8, columnspan=2, pady=10)

# Set row and column weights for resizing
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

add_frame = tk.LabelFrame(root, text="DB Adder")
add_frame.grid(row=2, column=0, padx=10, pady=10, sticky="we")

input_label = tk.Label(add_frame, text="URLs:")
input_label.grid(row=0, column=0, sticky="w")

input_text = tk.Text(add_frame, height=5, width=50)
input_text.grid(row=1, column=0, pady=5)
input_text.bind("<Control-c>", copy_selected_text)
input_text.bind("<Control-a>", select_all_text)

progress_bar = Progressbar(add_frame, orient="horizontal", mode="determinate")
progress_bar.grid(row=2, column=0, pady=5, padx=10, sticky="ew")

add_button = tk.Button(add_frame, text="Add to Database", command=add_to_database_background)
add_button.grid(row=3, column=0, pady=5, sticky="we")

network_frame = tk.LabelFrame(root, text="Generate Network@HTML")
network_frame.grid(row=3, column=0, padx=10, pady=10, sticky="we")

network_button = tk.Button(network_frame, text="Generate Network", command=generate_network_html)
network_button.pack(pady=5)

# Visualizer Frame
visualizer_frame = tk.LabelFrame(root, text="Comment Thread Visualizer")
visualizer_frame.grid(row=4, column=0, padx=10, pady=10, sticky="we")

#thread_id_label = tk.Label(visualizer_frame, text="Thread ID:")
#thread_id_label.grid(row=0, column=0, sticky="w")

def handle_visualizer_entry_focus_in(event):
    if thread_id_entry.get() == "Thread ID":
        thread_id_entry.delete(0, tk.END)
        thread_id_entry.config(foreground="black")

def handle_visualizer_entry_focus_out(event):
    if thread_id_entry.get() == "":
        thread_id_entry.insert(0, "Thread ID")
        thread_id_entry.config(foreground="gray")

thread_id_entry = tk.Entry(visualizer_frame)
thread_id_entry.pack(pady=5)
thread_id_entry.insert(0, "Thread ID")
thread_id_entry.config(foreground="gray")
thread_id_entry.bind("<FocusIn>", handle_visualizer_entry_focus_in)
thread_id_entry.bind("<FocusOut>", handle_visualizer_entry_focus_out)
thread_id_entry.bind("<Control-c>", copy_selected_text)
thread_id_entry.bind("<Control-a>", select_all_text)

visualizer_button = tk.Button(visualizer_frame, text="View Comment Thread", command=view_comment_thread_background)
visualizer_button.pack(pady=5)

check_frame = tk.LabelFrame(root, text="Check DB")
check_frame.grid(row=5, column=0, padx=10, pady=10, sticky="we")

search_label = tk.Label(check_frame, text="Search Query:")
search_label.grid(row=0, column=0, sticky="w")

search_entry = tk.Entry(check_frame)
search_entry.grid(row=0, column=1, pady=5)
search_entry.bind("<Control-c>", copy_selected_text)
search_entry.bind("<Control-a>", select_all_text)

blacklist_label = tk.Label(check_frame, text="Blacklist:")
blacklist_label.grid(row=1, column=0, sticky="w")
#blacklist_label.grid_remove()  # Initially hide the blacklist label

blacklist_entry = tk.Entry(check_frame)
blacklist_entry.grid(row=1, column=1, pady=5)
blacklist_entry.insert(0, "Enter channel ID")
blacklist_entry.config(foreground="gray")
blacklist_entry.bind("<Control-c>", copy_selected_text)
blacklist_entry.bind("<Control-a>", select_all_text)
#blacklist_entry.grid_remove()  # Initially hide the blacklist entry

search_type_label = tk.Label(check_frame, text="Search Type:")
search_type_label.grid(row=2, column=0, sticky="w")

search_type_var = tk.StringVar(value="thread")  # Set "thread" as the default value
search_type_dropdown = tk.OptionMenu(check_frame, search_type_var, "user", "thread", "comment")
search_type_dropdown.grid(row=2, column=1, pady=5)

# Add explanation labels for each search type
explanation_label = tk.Label(check_frame, text="", wraplength=300, justify="left")
explanation_label.grid(row=3, columnspan=2, padx=5, pady=5, sticky="w")

# Placeholder text dictionary for different search types
placeholder_texts = {
    "user": "Enter channel ID",
    "thread": "Enter thread ID",
    "comment": "Enter search text"
}

# Function to update the explanation label based on the selected search type
def update_explanation_label(*args):
    selected_type = search_type_var.get()
    if selected_type == "user":
        explanation_text = "Search for threads containing the given Channel ID."
    elif selected_type == "thread":
        explanation_text = "Search threads that contain the same Channel IDs."
    elif selected_type == "comment":
        explanation_text = "Search all threads for comments that match the provided text."

    explanation_label.config(text=explanation_text)

search_type_var.trace_add("write", update_explanation_label)
update_explanation_label()  # Update the explanation label initially

# Function to update the search query entry placeholder text
def update_placeholder_text(*args):
    selected_type = search_type_var.get()
    placeholder_text = placeholder_texts.get(selected_type, "")
    search_entry.delete(0, tk.END)
    search_entry.insert(0, placeholder_text)
    if search_entry.get() == placeholder_text:
        search_entry.config(foreground="gray")
    else:
        search_entry.config(foreground="black")

search_type_var.trace_add("write", update_placeholder_text)
update_placeholder_text()  # Update the placeholder text initially

# Function to handle the focus events of the search query entry field
def handle_entry_focus_in(event):
    if search_entry.get() == placeholder_texts[search_type_var.get()]:
        search_entry.delete(0, tk.END)
        search_entry.config(foreground="black")

def handle_entry_focus_out(event):
    if search_entry.get() == "":
        selected_type = search_type_var.get()
        search_entry.insert(0, placeholder_texts[selected_type])
        search_entry.config(foreground="gray")

search_entry.bind("<FocusIn>", handle_entry_focus_in)
search_entry.bind("<FocusOut>", handle_entry_focus_out)

# Function to handle the focus events of the blacklist entry field
def handle_blacklist_focus_in(event):
    if blacklist_entry.get() == "Enter channel ID":
        blacklist_entry.delete(0, tk.END)
        blacklist_entry.config(foreground="black")

def handle_blacklist_focus_out(event):
    if blacklist_entry.get() == "":
        blacklist_entry.insert(0, "Enter channel ID")
        blacklist_entry.config(foreground="gray")

search_type_var.trace_add("write", lambda *args: blacklist_label.grid() if search_type_var.get() == "thread" else blacklist_label.grid_remove())
search_type_var.trace_add("write", lambda *args: blacklist_entry.grid() if search_type_var.get() == "thread" else blacklist_entry.grid_remove())
blacklist_entry.bind("<FocusIn>", handle_blacklist_focus_in)
blacklist_entry.bind("<FocusOut>", handle_blacklist_focus_out)

search_button = tk.Button(check_frame, text="Search", command=check_database_background)
search_button.grid(row=4, columnspan=2, pady=5, sticky="we")

output_frame = tk.Frame(root)
output_frame.grid(row=6, column=0, padx=10, pady=10, sticky="we")

output_text = tk.Text(output_frame, height=5, width=30)
output_text.pack(fill="both")
output_text.bind("<Control-c>", copy_selected_text)
output_text.bind("<Control-a>", select_all_text)

root.mainloop()
