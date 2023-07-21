# -*- coding: utf-8 -*-

# Sample Python code for youtube.commentThreads.list
# See instructions for running these code samples locally:
# https://developers.google.com/explorer-help/code-samples#python

import os
import psycopg2
from psycopg2 import extras
import json
import googleapiclient.discovery
from operator import itemgetter
import colorsys
import time
import re
from fuzzywuzzy import fuzz
from jinja2 import Template
import urllib.request

conn = None
cur = None
settings = None

def initiate_db():
    global settings
    global conn
    global cur
    # Load settings from file or create default settings
    try:
        with open("settings.json", "r") as f:
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
    
    DB_Host = settings["db_url"]
    DB_Name = settings["db_name"]
    DB_User = settings["db_user"]
    DB_Pass = settings["db_pass"]
    
    # Establish a connection to the database
    conn = psycopg2.connect(
        host=DB_Host,
        database=DB_Name,
        user=DB_User,
        password=DB_Pass
    )
    
    # Create a cursor
    cur = conn.cursor(cursor_factory=extras.DictCursor)
    
    # Create the Threads table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Threads (
            ThreadID TEXT PRIMARY KEY,
            VideoID TEXT,
            Description TEXT,
            Tags TEXT[],
            Thread JSONB,
            ChannelIDs TEXT[]
        )
    """)
    
    # Create the Videos table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Videos (
            VideoID TEXT PRIMARY KEY,
            Title TEXT[],
            Description TEXT[],
            CommentCount INT,
            Views INT,
            ThreadIDs TEXT[]
        )
    """)
    
    # Create the Users table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            ChannelID TEXT PRIMARY KEY,
            ProfilePictures TEXT[],
            Usernames TEXT[],
            ThreadIDs TEXT[],
            Description TEXT,
            Color TEXT
        )
    """)
    
    # Commit the changes
    conn.commit()

initiate_db()

def api_retrieve_thread(id, update_output=None, clear_output=None, update_progressbar=None, get_input_values=None):
    global settings
    # Disable OAuthlib's HTTPS verification when running locally.
    # *DO NOT* leave this option enabled in production.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    YT_DEVELOPER_KEY = settings["api_key"]

    youtube = googleapiclient.discovery.build(
        api_service_name, api_version, developerKey=DEVELOPER_KEY)

    response = {
        "items": []
    }
    nextPageToken = None
    request = youtube.commentThreads().list(
        part="snippet",
        id=id,
        maxResults=1,
        moderationStatus="rejected",
        order="time"
    )
    topLevelComment = request.execute()
    # Check if topLevelComment is empty
    if "items" not in topLevelComment or len(topLevelComment["items"]) == 0:
        return topLevelComment
    while True:
        request = youtube.comments().list(
            part="snippet",
            maxResults=100,
            parentId=id,
            pageToken=nextPageToken
        )
        result = request.execute()

        items = result.get("items", [])
        response["items"].extend(items)

        nextPageToken = result.get("nextPageToken")
        if not nextPageToken:
            break
    
    # Retrieve video information
    video_request = youtube.videos().list(
        part="snippet,statistics",
        id=topLevelComment["items"][0]["snippet"]["videoId"]
    )
    video_response = video_request.execute()

    # Extract video details
    video_info = video_response["items"][0]["snippet"]
    video_statistics = video_response["items"][0]["statistics"]
    
    # Reorder the response items from oldest to newest based on publishedAt timestamp
    response["items"].sort(key=lambda x: x["snippet"]["publishedAt"])

    # Add topLevelComment to the start of the thread
    if "items" in topLevelComment and len(topLevelComment["items"]) > 0:  # If top-level comment isn't deleted
        topLevelComment["items"][0]["replies"] = {"comments": []}
        topLevelComment["items"][0]["replies"]["comments"].extend(response["items"])

    # Add video information to topLevelComment
    topLevelComment["items"][0]["videoDetails"] = {
        "title": video_info["title"],
        "description": video_info["description"],
        "uploadDate": video_info["publishedAt"],
        "commentCount": video_statistics["commentCount"],
        "viewCount": video_statistics["viewCount"],
        "likeCount": video_statistics["likeCount"]
    }

    return topLevelComment


def process_and_save_data(response, update_output=None, clear_output=None, update_progressbar=None, get_input_values=None):
    global cur
    global conn
    
    # Create the comments variable
    comments = []
    pfp_urls = {}
    # Save toplevelcomment url
    pfp_urls[response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"]] = response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorProfileImageUrl"]
    
    videoID = response["items"][0]["snippet"]["videoId"]
    threadID = response["items"][0]["id"]
    # Execute the query to check if the threadID exists in the database
    cur.execute("""
        SELECT Thread
        FROM Threads
        WHERE ThreadID = %s
    """, (threadID,))   
    
    # Fetch the result
    existing_thread = cur.fetchone()
    
    # Execute the query to check if the videoID exists in the database
    cur.execute("""
        SELECT *
        FROM Videos
        WHERE VideoID = %s
    """, (videoID,))   
    
    # Fetch the result
    existing_video = [dict(row) for row in cur.fetchall()]
    
    # Extract Video information
    videoDetails = response["items"][0]["videoDetails"]
    video = {
        'Title': videoDetails["title"],
        'Description': videoDetails["description"],
        'Upload_Date': videoDetails["uploadDate"],
        'Comment_Count': videoDetails["commentCount"],
        'Views': videoDetails["viewCount"],
        'Likes': videoDetails["likeCount"]
    }
    
    if existing_thread is not None:
        existing_comments = existing_thread[0]
        # Thread already exists in the database
        # Perform actions for an existing thread
        old_comments = []
        new_comments = []
        allAPIIDs = []
        allAPIMSGs = []
        allDatabaseIDs = []
        allDatabaseMSGs = []
        # Add all the messages and IDs to arrays for easy checking
        for existing_comment in existing_comments: # loop through database existing_comments[index]
            allDatabaseIDs.append(existing_comment["CommentID"])
            allDatabaseMSGs.append(existing_comment["Comment"])
        allAPIIDs.append(response["items"][0]["snippet"]["topLevelComment"]["id"])
        allAPIMSGs.append(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"])
        for comment in response["items"][0]["replies"]["comments"]: # loop through API response
            pfp_urls[comment["snippet"]["authorChannelId"]["value"]] = comment["snippet"]["authorProfileImageUrl"]
            allAPIIDs.append(comment["id"])
            allAPIMSGs.append(comment["snippet"]["textDisplay"])
        
        # Check the database (unchanged, edited, deleted)
        for existing_comment in existing_comments: 
            if existing_comment["CommentID"] in allAPIIDs:
                # ID Matches
                comment_index = allAPIIDs.index(existing_comment["CommentID"]) # Retrieve index of the matching ID
                if comment_index - 1 == -1:  # OP comment
                    updated_at_array = list(set([str(date) for date in existing_comment["UpdateDate"]] +
                                                [str(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["updatedAt"])]))
                else:
                    updated_at_array = list(set([str(date) for date in existing_comment["UpdateDate"]] +
                                                [str(response["items"][0]["replies"]["comments"][comment_index - 1]["snippet"]["updatedAt"])]))
                updated_at_array.sort()             
                if allAPIMSGs[comment_index] == existing_comment["Comment"]: # Get the comment for the matching ID
                    # Message unchanged
                    # Message and ID matches database
                    # Save API message over database message
                    if comment_index-1 == -1: # OP comment
                        post = add_comment(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"], response["items"][0]["snippet"]["topLevelComment"]["id"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["likeCount"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"], updated_at_array, False)
                    else:
                        post = add_comment(response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorChannelId"]["value"], response["items"][0]["replies"]["comments"][comment_index-1]["id"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorDisplayName"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["likeCount"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["publishedAt"], updated_at_array, False)
                    old_comments.append(post)
                else:
                    # Message edited
                    # Message edited but ID matches database
                    # Save API message with old message from database in a array containing all old messages
                    if comment_index-1 == -1: # OP comment
                        post = add_comment(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"], response["items"][0]["snippet"]["topLevelComment"]["id"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["likeCount"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"], updated_at_array, False)
                    else:
                        post = add_comment(response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorChannelId"]["value"], response["items"][0]["replies"]["comments"][comment_index-1]["id"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorDisplayName"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["likeCount"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["publishedAt"], updated_at_array, False)
                    post["Comment_History"].append(existing_comment["Comment"]) # Add the old version of the comment
                    old_comments.append(post)
            else:
                # Deleted message
                # If the comment ID is in the database but couldn't be found in the API response
                # Save database message
                post = add_comment(existing_comment["ChannelID"], existing_comment["CommentID"], existing_comment["Username"], existing_comment["Comment"], existing_comment["Comment_History"], existing_comment["Likes"], existing_comment["PostDate"], existing_comment["UpdateDate"], True)
                old_comments.append(post)
        # Check the API (new)
        for comment in response["items"][0]["replies"]["comments"]:
            if comment["id"] not in allDatabaseIDs:
                # New message
                # Comment ID not found in database
                # Save comment  
                new_comments.append(add_comment(comment["snippet"]["authorChannelId"]["value"], comment["id"], comment["snippet"]["authorDisplayName"], comment["snippet"]["textDisplay"], [], comment["snippet"]["likeCount"], comment["snippet"]["publishedAt"], [comment["snippet"]["updatedAt"]], False))
        
        # Print the categorized comments
        for comment in new_comments:
            print("New Comment:")
            print(comment)
        
        if update_output is not None:
            for index, comment in enumerate(old_comments):
                if comment["Deleted"]:
                    update_output("Deleted comment:")
                elif comment["Comment_History"] != existing_comments[index]["Comment_History"]:
                    update_output("Edited comment:")
                else:
                    update_output("Unmodified comment:")
                update_output(comment)  
        else:
            for index, comment in enumerate(old_comments):
                if comment["Deleted"]:
                    print("Deleted comment:")
                elif comment["Comment_History"] != existing_comments[index]["Comment_History"]:
                    print("Edited comment:")
                else:
                    print("Unmodified comment:")
                print(comment)  
        comments = old_comments + new_comments
    else:
        # Thread does not exist in the database
        # Perform actions for a new thread
        
        # Extract OP comment information
        op_comment = {
            'ChannelID': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"],
            'CommentID': response["items"][0]["snippet"]["topLevelComment"]["id"],
            'Username': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"],
            'Comment': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"],
            'Comment_History': [],	
            'Likes': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["likeCount"],
            'PostDate': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"],
            'UpdateDate': [response["items"][0]["snippet"]["topLevelComment"]["snippet"]["updatedAt"]],
            'Deleted': False
        }
        comments.append(op_comment)
        
        # Extract reply comments information
        replies = response["items"][0]["replies"]["comments"]
        for reply in replies:
            pfp_urls[reply["snippet"]["authorChannelId"]["value"]] = reply["snippet"]["authorProfileImageUrl"]
            reply_comment = {
                'ChannelID': reply["snippet"]["authorChannelId"]["value"],
                'CommentID': reply["id"],
                'Username': reply["snippet"]["authorDisplayName"], 
                'Comment': reply["snippet"]["textDisplay"],	
                'Comment_History': [],
                'Likes': reply["snippet"]["likeCount"],
                'PostDate': reply["snippet"]["publishedAt"],
                'UpdateDate': [reply["snippet"]["updatedAt"]],
                'Deleted': False
            }
            comments.append(reply_comment)
        if update_output is not None:
            update_output(comments)
        else:
            print(comments)
    comments_json = json.dumps(comments)
    channelIDs = set(comment['ChannelID'] for comment in comments)
    # Insert a new row into Threads table, update if threadID already exists
    cur.execute("""
        INSERT INTO Threads (VideoID, ThreadID, Thread, ChannelIDs)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ThreadID)
        DO UPDATE SET
            Thread = excluded.Thread,
            ChannelIDs = excluded.ChannelIDs
    """, (videoID, threadID, comments_json, list(channelIDs)))  
     
    # User database generate/update code starts here
    users = {}
    print("Profile picture URL dict: ", pfp_urls)
    for comment in comments:
        channel_id = comment["ChannelID"]
        profile_picture = pfp_urls[comment["ChannelID"]]
        username = comment["Username"]
    
        if channel_id not in users:
            users[channel_id] = {
                "ChannelID": channel_id,
                "ProfilePictures": [],
                "Usernames": [],
                "ThreadIDs": []
            }
    
        if profile_picture not in users[channel_id]["ProfilePictures"]:
            users[channel_id]["ProfilePictures"].append(profile_picture)
    
        if username not in users[channel_id]["Usernames"]:
            users[channel_id]["Usernames"].append(username)
            
        if threadID not in users[channel_id]["ThreadIDs"]:
            users[channel_id]["ThreadIDs"].append(threadID)
    
    # Check the users database and update existing records if necessary
    for user in users.values():
        channel_id = user["ChannelID"]
        existing_record = cur.execute("SELECT * FROM Users WHERE ChannelID = %s", (channel_id,))
        if existing_record:
            old_profile_pictures = existing_record["ProfilePictures"]
            old_usernames = existing_record["Usernames"]
            old_threads = existing_record["ThreadIDs"]
    
            new_profile_pictures = user["ProfilePictures"]
            new_usernames = user["Usernames"]
            new_threads = user["ThreadIDs"]
    
            user["ProfilePictures"] = list(set(old_profile_pictures + new_profile_pictures))
            user["Usernames"] = list(set(old_usernames + new_usernames))
            user["ThreadIDs"] = list(set(old_threads + new_threads))
    
        cur.execute(
            "INSERT INTO Users (ChannelID, ProfilePictures, Usernames, ThreadIDs) VALUES (%s, %s, %s, %s) ON CONFLICT (ChannelID) DO UPDATE SET ProfilePictures = %s, Usernames = %s, ThreadIDs = %s", 
            (channel_id, user["ProfilePictures"], user["Usernames"], user["ThreadIDs"], user["ProfilePictures"], user["Usernames"], user["ThreadIDs"])
        )
    
    # Video database generate/update code starts here
    
    # Fetch the ThreadIDs for threads that match the VideoID
    cur.execute("SELECT ThreadID FROM Threads WHERE VideoID = %s", (videoID,))
    thread_ids_list = cur.fetchall()
    
    # Combine the ThreadIDs into one list while preventing duplicates
    combined_thread_ids = list(set([thread_id for sublist in thread_ids_list for thread_id in sublist]))
    
    # Append the new thread ID if it's not already in the list
    if threadID not in combined_thread_ids:
        combined_thread_ids.append(threadID)
    
    print(combined_thread_ids)
    if existing_video:
        existing_video = existing_video[0]
        
        # Video already exists, update the title and description arrays
        title_array = list(set(existing_video["title"] + [video['Title']]))
        description_array = list(set(existing_video["description"] + [video['Description']]))
        
        cur.execute("UPDATE Videos SET Title = %s, Description = %s, ThreadIDs = %s WHERE VideoID = %s", (title_array, description_array, combined_thread_ids, videoID))
    else:
        # Video doesn't exist, insert a new row
        cur.execute("INSERT INTO Videos (VideoID, Title, Description, CommentCount, Views, ThreadIDs) VALUES (%s, %s, %s, %s, %s, %s)",
                    (videoID, [video['Title']], [video['Description']], video['Comment_Count'], video['Views'], combined_thread_ids))
        
    conn.commit()
    return comments

def download_image(image_url, image_path):
    # Check if the image has already been downloaded
    if not os.path.exists(image_path):
        try:
            # Download the image
            with urllib.request.urlopen(image_url) as response, open(image_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Error downloading image: {e}")

def create_vis_network(update_output=None, clear_output=None, update_progressbar=None, get_input_values=None):
    global cur
    global conn
    global settings
    # Fetch data from the Users table
    cur.execute("SELECT * FROM Users")
    user_data = [dict(row) for row in cur.fetchall()]

    # Fetch data from the Threads table
    cur.execute("SELECT * FROM Threads")
    thread_data = [dict(row) for row in cur.fetchall()]

    # Fetch data from the Videos table
    cur.execute("SELECT VideoID, Title, Description, CommentCount, Views, ThreadIDs FROM Videos")
    video_data_rows = cur.fetchall()
    
    # Format the fetched data into a dictionary
    video_data = {}
    for row in video_data_rows:
        video_id = row[0]
        title = row[1]
        description = row[2]
        comment_count = row[3]
        views = row[4]
        thread_ids = row[5]
    
        video_data[video_id] = {
            "videoid": video_id,
            "title": title,
            "description": description,
            "commentcount": comment_count,
            "views": views,
            "threadids": thread_ids
        }

    # Create empty lists to hold nodes and edges
    nodes = []
    edges = []
    
    comment_thread_color = "#0bb400"  # Green
    user_color = "#00b4a9"  # Blue
    video_color = "#b4a900"  # Yellow
    brightness_shift = 0.8
    
    # Loop through user data and create user nodes
    for user in user_data:
        channel_id = user["channelid"]
        profile_pictures = user["profilepictures"]
        usernames = user["usernames"]
        thread_ids = user["threadids"]
        description = user["description"] or ""
        custom_color = user["color"] or ""
        
        if custom_color != "":
            user_color = custom_color # Use custom color if it's set for that user
            # TODO: Create custom user shapes?
        
        # Create a unique node ID for the user
        node_id = f"user_{channel_id}"
        
        if settings["enable_cache"]:
            # Download the user's profile picture if not downloaded already
            image_url = profile_pictures[0]
            image_path = f"images/{channel_id}.jpg"
            download_image(image_url, image_path)
            # Set node PFP to local version
            profile_picture = f"images/{channel_id}.jpg"  # Add 'f' before the string to format it correctly
        else:
            # Set node PFP to web version
            profile_picture = profile_pictures[0]
        
        # Create the user node
        user_node = {
            "id": node_id,
            "label": usernames[0],  # Assuming the first username is the primary one
            "group": "user",
            "image": profile_picture,  # Use local path for the image
            "url": f"https://www.youtube.com/channel/{channel_id}",
            "profilepictures": profile_pictures,
            "usernames": usernames,
            "description": description,
            "color": {
                "border": user_color, # Border color of node
                "background": user_color, # Background color of node
                "highlight": {
                    "border": user_color, # Border color when node is highlighted
                    "background": modify_hex_color(user_color, brightness_shift) # Background color when node is highlighted
                }
            }
        }

        # Add the user node to the nodes list
        nodes.append(user_node)
    
    for video in video_data:
        # Create a unique node ID for the thread
        video_node_id = f"video_{video_data[video_id]['videoid']}"
        video_id = video
        # Create the thread node
        video_node = {
            "id": video_node_id,
            "label": video_data[video_id]['title'][0],
            "group": "video",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "titles": video_data[video_id]['title'],
            "views": video_data[video_id]['views'],
            "commentcount": video_data[video_id]['commentcount'],
            "threadids": video_data[video_id]['threadids'],
            "description": video_data[video_id]['description'],
            "color": {
                "border": video_color, # Border color of node
                "background": video_color, # Background color of node
                "highlight": {
                    "border": video_color, # Border color when node is highlighted
                    "background": modify_hex_color(video_color, brightness_shift) # Background color when node is highlighted
                }
            }       
        }
        for thread in video_data[video_id]['threadids']:
            thread_node_id = f"thread_{thread}"
            video_edge = {
                "from": video_node_id,
                "to": thread_node_id,
                "color": {
                    "color": mix_hex_colors(video_color, comment_thread_color), # Color of the edge
                    "highlight": modify_hex_color(mix_hex_colors(video_color, comment_thread_color), brightness_shift) # Color of the edge on highlight
                }
            }
            edges.append(video_edge)
    
        # Add the thread node to the nodes list
        nodes.append(video_node)

    # Loop through thread data and create thread nodes and edges
    for thread in thread_data:
        # Extract thread information
        thread_id = thread["threadid"]
        video_id = thread["videoid"]
        description = thread["description"] or ""
        tags = thread["tags"] or []
        channel_ids = thread["channelids"]
    
        # Convert tags and channel_ids to lists if they are not already
        if not isinstance(tags, list):
            tags = [tags]
        if not isinstance(channel_ids, list):
            channel_ids = [channel_ids]
    
        # Create a unique node ID for the thread
        thread_node_id = f"thread_{thread_id}"
    
        # Create the thread node
        thread_node = {
            "id": thread_node_id,
            "label": f"{thread_id}",
            "group": "thread",
            "url": f"https://www.youtube.com/watch?v={video_id}&lc={thread_id}",
            "description": description,
            "tags": tags,
            "color": {
                "border": comment_thread_color, # Border color of node
                "background": comment_thread_color, # Background color of node
                "highlight": {
                    "border": comment_thread_color, # Border color when node is highlighted
                    "background": modify_hex_color(comment_thread_color, brightness_shift) # Background color when node is highlighted
                }
            }       
        }
    
        # Add the thread node to the nodes list
        nodes.append(thread_node)
        
        # Create edges connecting thread nodes to user nodes
        for channel_id in channel_ids:
            user_node_id = f"user_{channel_id}"
            edge = {
                "from": user_node_id,
                "to": thread_node_id,
                "color": {
                    "color": mix_hex_colors(user_color, comment_thread_color), # Color of the edge
                    "highlight": modify_hex_color(mix_hex_colors(user_color, comment_thread_color), brightness_shift) # Color of the edge on highlight
                }
            }
            edges.append(edge)

    # Create a dictionary with the nodes and edges
    network_data = {
        "nodes": nodes,
        "edges": edges
    }
    
    # Convert nodes and edges to JSON strings
    nodes_str = json.dumps(network_data["nodes"])
    edges_str = json.dumps(network_data["edges"])
    
    # Save nodes and edges to file
    with open("nodes.txt", "w") as file:
        file.write("const nodes = " + nodes_str + ";")
        file.write("\n\n")
        file.write("const edges = " + edges_str + ";")

    # Load the indexExample.html file
    with open("indexTemplate.html") as file:
        html_template = Template(file.read())

    # Render the template with the network data
    rendered_html = html_template.render(nodes=json.dumps(network_data["nodes"]), edges=json.dumps(network_data["edges"]))

    # Save the rendered HTML to a new file or overwrite the existing one
    with open("index.html", "w") as file:
        file.write(rendered_html)

    return network_data

def search_db(search_query, blacklist, search_type, returnresults_str):
    global cur
    global conn

    if search_type == "user":
        # Search the Threads database for thread IDs that contain the given channel ID in their channelids array
        cur.execute("SELECT ThreadID FROM Threads WHERE %s = ANY (ChannelIDs)", (search_query,))
        thread_ids = cur.fetchall()
        return [thread_id[0] for thread_id in thread_ids]

    elif search_type == "thread":
        # Determine the SQL query condition based on the presence of blacklist
        cur.execute("SELECT ChannelIDs FROM Threads WHERE ThreadID = %s", (search_query,))
    
        channel_ids = cur.fetchone()
        if channel_ids is not None:
            channel_ids = channel_ids[0]
            filtered_channel_ids = []
            for channel_id in channel_ids:
                # Exclude blacklisted channels from the filtered channel IDs
                if channel_id not in blacklist:
                    filtered_channel_ids.append(channel_id)
            # Search all other threads for any filtered channel ID matches
            cur.execute("SELECT ThreadID FROM Threads WHERE %s && ChannelIDs", (filtered_channel_ids,))
            thread_ids = cur.fetchall()
            return [thread_id[0] for thread_id in thread_ids]
        else:
            return []
        
    elif search_type == "comment":
        try:
            returnresults = int(returnresults_str)
        except ValueError:
            # Handle the exception
            returnresults = 10
        cur.execute("SELECT Thread FROM Threads")
        threads = cur.fetchall()
        matching_comments = []
        for thread in threads:
            comments = thread[0]
            for comment in comments:
                comment_text = comment.get("Comment", "")
                
                # Remove special characters from the comment and search query
                comment_text_cleaned = re.sub(r"[^\w\s]", "", comment_text)
                search_query_cleaned = re.sub(r"[^\w\s]", "", search_query)
                
                # Tokenize the cleaned comment and search query into individual words
                comment_words = comment_text_cleaned.lower().split()
                search_words = search_query_cleaned.lower().split()
                
                # Find the common words between the comment and search query
                common_words = [word for word in comment_words if word in search_words]
                
                # Calculate the ratio based on the common words
                similarity_ratio = fuzz.ratio(" ".join(common_words), search_query_cleaned.lower())
                
                if similarity_ratio >= 5:  # Set a threshold for similarity
                    matching_comments.append(comment)
        
        # Sort comments based on the ratio calculated from common words
        top_similar_comments = sorted(matching_comments, key=lambda x: fuzz.ratio(" ".join(re.sub(r"[^\w\s]", "", x.get("Comment", "")).lower().split()), search_query_cleaned.lower()), reverse=True)[:returnresults]
        return top_similar_comments

    else:
        return []  # Invalid search type


def add_comment(ChannelID, CommentID, Username, Comment, Comment_History, Likes, PostDate, UpdateDate, Deleted):
    comment = {
        'ChannelID': ChannelID,
        'CommentID': CommentID,
        'Username': Username, 
        'Comment': Comment,	
        'Comment_History': Comment_History,	
        'Likes': Likes,
        'PostDate': PostDate,
        'UpdateDate': UpdateDate,
        'Deleted': Deleted
    }
    return comment

def modify_hex_color(hex_code, brightness_adjustment):
    # Initialize the cache dictionary if not already defined
    if not hasattr(modify_hex_color, "cache"):
        modify_hex_color.cache = {}

    # Check if the modification is already in the cache
    cache_key = (hex_code, brightness_adjustment)
    if cache_key in modify_hex_color.cache:
        return modify_hex_color.cache[cache_key]

    # Remove any leading '#' character if present
    hex_code = hex_code.lstrip('#')

    # Adjust the format of hex_code to 'RRGGBB' if necessary
    if len(hex_code) == 3:
        hex_code = hex_code[0] + hex_code[0] + hex_code[1] + hex_code[1] + hex_code[2] + hex_code[2]

    # Convert the hex code to RGB
    rgb = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

    # Convert RGB to HSV
    hsv = colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)

    # Adjust brightness and hue
    brightness_factor = brightness_adjustment * 0.5

    if brightness_adjustment > 0:
        hue_factor = 0.05
    elif brightness_adjustment < 0:
        hue_factor = -0.05
    else:
        hue_factor = 0

    modified_hsv = (hsv[0] + hue_factor, hsv[1], min(1.0, hsv[2] + brightness_factor))

    # Convert modified HSV back to RGB
    modified_rgb = colorsys.hsv_to_rgb(modified_hsv[0], modified_hsv[1], modified_hsv[2])

    # Convert modified RGB to hex code
    modified_hex = '#%02x%02x%02x' % (int(modified_rgb[0]*255), int(modified_rgb[1]*255), int(modified_rgb[2]*255))

    # Store the modification in the cache
    modify_hex_color.cache[cache_key] = modified_hex

    return modified_hex

def mix_hex_colors(hex_code1, hex_code2):
    # Initialize the cache dictionary if not already defined
    if not hasattr(mix_hex_colors, "cache"):
        mix_hex_colors.cache = {}

    # Check if the mix is already in the cache
    cache_key = (hex_code1, hex_code2)
    if cache_key in mix_hex_colors.cache:
        return mix_hex_colors.cache[cache_key]

    # Remove any leading '#' character if present
    hex_code1 = hex_code1.lstrip('#')
    hex_code2 = hex_code2.lstrip('#')

    # Adjust the format of hex_code to 'RRGGBB' if necessary
    if len(hex_code1) == 3:
        hex_code1 = hex_code1[0] + hex_code1[0] + hex_code1[1] + hex_code1[1] + hex_code1[2] + hex_code1[2]
    if len(hex_code2) == 3:
        hex_code2 = hex_code2[0] + hex_code2[0] + hex_code2[1] + hex_code2[1] + hex_code2[2] + hex_code2[2]

    # Convert the hex codes to RGB
    rgb1 = tuple(int(hex_code1[i:i+2], 16) for i in (0, 2, 4))
    rgb2 = tuple(int(hex_code2[i:i+2], 16) for i in (0, 2, 4))

    # Mix the RGB values
    mixed_rgb = tuple(int((c1 + c2) / 2) for c1, c2 in zip(rgb1, rgb2))

    # Convert mixed RGB to hex code
    mixed_hex = '#%02x%02x%02x' % mixed_rgb

    # Store the mix in the cache
    mix_hex_colors.cache[cache_key] = mixed_hex

    return mixed_hex

# Function to return a thread using it's ThreadID
def get_thread_by_id(thread_id):
    global cur
    global conn
    cur.execute("SELECT * FROM Threads WHERE ThreadID = %s", (thread_id,))
    thread_data = [dict(row) for row in cur.fetchall()]
    #for comment in thread:
        #print(comment["Username"])
    if thread_data:
        thread = thread_data[0]["thread"]
        return thread
    else:
        return None

# Dictionary to cache user profile picture URLs
user_cache = {}

# Function to find a user's profile picture URL using ChannelID
def get_profile_picture_url(channel_id):
    # Check if the user is in the cache
    if channel_id in user_cache:
        return user_cache[channel_id]
    
    global cur
    global conn
    # If the user is not in the cache, query the database
    cur.execute("SELECT ProfilePictures FROM Users WHERE ChannelID = %s", (channel_id,))
    result = cur.fetchone()

    if result:
        profile_pictures = result[0]
        if profile_pictures:
            # Get the first URL from the profilepictures array
            profile_picture_url = profile_pictures[0]

            # Add the user to the cache
            user_cache[channel_id] = profile_picture_url

            # If the cache size exceeds 20, remove the oldest entry
            if len(user_cache) > 20:
                oldest_key = next(iter(user_cache.keys()))
                del user_cache[oldest_key]

            return profile_picture_url

    return None

if __name__ == "__main__": # Directly ran
    threads = []
    while threads:
        thread = threads.pop(0)  # Get the first API string from the array and remove it
        print(thread)
        api_response = api_retrieve_thread(thread)
        json_object = json.dumps(api_response, indent=4)
        with open('api.json', 'w') as f:
            f.write(json_object)
        if "items" in api_response and len(api_response["items"]) > 0:  # If toplevel comment isn't deleted
            comments = process_and_save_data(api_response)
        time.sleep(2)
    vis_network_data = create_vis_network()
    #threads = [""]
    #while threads:
    #    thread = threads.pop(0)  # Get the first API string from the array and remove it
    #    print(thread)
    #    api_response = api_retrieve_thread(thread)
    #    json_object = json.dumps(api_response, indent=4)
    #    with open('api.json', 'w') as f:
    #        f.write(json_object)
    #    if "items" in api_response and len(api_response["items"]) > 0:  # If toplevel comment isn't deleted
    #        comments = process_and_save_data(api_response)
    #    time.sleep(2)
    #vis_network_data = create_vis_network()
    #print(vis_network_data["nodes"])
    #print("\n\n")
    #print(vis_network_data["edges"])
    # Print the recreated comments variable
    #print(comments)
    # Close the cursor and the connection
    cur.close()
    conn.close()

