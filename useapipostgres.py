# -*- coding: utf-8 -*-

# Sample Python code for youtube.commentThreads.list
# See instructions for running these code samples locally:
# https://developers.google.com/explorer-help/code-samples#python

import os
import psycopg2
import json
import googleapiclient.discovery
from operator import itemgetter

# Establish a connection to the database
conn = psycopg2.connect(
    host="localhost",
    database="database_name",
    user="put_username",
    password="put_password"
)

# Create a cursor
cur = conn.cursor()

# Create the Threads table if it doesn't exist
cur.execute("""
    CREATE TABLE IF NOT EXISTS Threads (
        ThreadID VARCHAR(255) PRIMARY KEY,
        VideoID VARCHAR(255),
        Description TEXT,
        Tags TEXT[],
        Thread JSONB,
        ChannelIDs TEXT[]
    )
""")

# Create the Users table if it doesn't exist
cur.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        ChannelID VARCHAR(255) PRIMARY KEY,
        ProfilePictures TEXT[],
        Usernames TEXT[],
        Description TEXT,
        Color VARCHAR(255)
    )
""")

# Commit the changes
conn.commit()

def api_retrieve_thread(id):
    # Disable OAuthlib's HTTPS verification when running locally.
    # *DO NOT* leave this option enabled in production.
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    DEVELOPER_KEY = "PUT_DEV_KEY_HERE"

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
    # Reorder the response items from oldest to newest based on publishedAt timestamp
    response["items"].sort(key=lambda x: x["snippet"]["publishedAt"])
    
    # Add topLevelComment to the start of the thread
    if "items" in topLevelComment and len(topLevelComment["items"]) > 0: # If toplevel comment isn't deleted
        topLevelComment["items"][0]["replies"] = {"comments": []}
        topLevelComment["items"][0]["replies"]["comments"].extend(response["items"])
    return topLevelComment

def process_and_save_data(response):
    global cur
    global conn
    # TODO: Check if thread exists at the start
    # TODO: if thread exists check if comments in the response already exist in the database, skip any that do, add any comments that don't exist to the comments dictionary.
    # TODO: Check if there are comments in the database that don't exist in the response, if anything matches add the deleted:yes parameter to that comment
    # TODO: Add message edit history if comment was modified
    # TODO: Add message ID to each message. 
    # If response message ID doesn't exist in database == new
    # If response message doesn't match message in database but ID is same == new edited
    # If database message ID doesn't exist in response == deleted
    # If database message doesn't match message in response but ID is same == old edited
    # Create the comments variable
    comments = []
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
    
    if existing_thread is not None:
        existing_comments = existing_thread[0]
        # Thread already exists in the database
        # Perform actions for an existing thread
        
        # API Message ID (OP)
        #response["items"][0]["snippet"]["topLevelComment"]["id"]
        # API Comment (OP)
        #response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
        
        # API Message ID (Index)
        #response["items"][0]["replies"]["comments"][index]["id"]
        # API Comment (Index) 
        #response["items"][0]["replies"]["comments"][index]["snippet"]["textDisplay"]
        
        # Database message id (OP)
        #existing_comments[0]['CommentID']
        # Database Comment (OP)
        #existing_comments[0]['Comment']
        
        # Database message id (Index)
        #existing_comments[index]['CommentID']
        # Database Comment (Index)
        #existing_comments[index]['Comment']
        
        # If API response message ID doesn't exist in database == new
        # If API response message doesn't match message in database but ID is same == new edited
        # If database message ID doesn't exist in API Response == deleted
        # If database message doesn't match message in API Response but ID is same == old edited
            
    
        # Check for new messages
        # Check for edited messages
        # Check for deleted messages
        
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
            allAPIIDs.append(comment["id"])
            allAPIMSGs.append(comment["snippet"]["textDisplay"])
        
        # Check the database (unchanged, edited, deleted)
        for existing_comment in existing_comments: 
            if existing_comment["CommentID"] in allAPIIDs:
                # ID Matches
                comment_index = allAPIIDs.index(existing_comment["CommentID"]) # Retrieve index of the matching ID
                if allAPIMSGs[comment_index] == existing_comment["Comment"]: # Get the comment for the matching ID
                    # Message unchanged
                    # Message and ID matches database
                    # Save API message over database message
                    if comment_index-1 == -1: # OP comment
                        post = add_comment(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"], response["items"][0]["snippet"]["topLevelComment"]["id"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["likeCount"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["updatedAt"], False)
                    else:
                        post = add_comment(response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorChannelId"]["value"], response["items"][0]["replies"]["comments"][comment_index-1]["id"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorDisplayName"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["likeCount"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["publishedAt"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["updatedAt"], False)
                    old_comments.append(post)
                else:
                    # Message edited
                    # Message edited but ID matches database
                    # Save API message with old message from database in a array containing all old messages
                    if comment_index-1 == -1: # OP comment
                        post = add_comment(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"], response["items"][0]["snippet"]["topLevelComment"]["id"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["likeCount"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"], response["items"][0]["snippet"]["topLevelComment"]["snippet"]["updatedAt"], False)
                    else:
                        post = add_comment(response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorChannelId"]["value"], response["items"][0]["replies"]["comments"][comment_index-1]["id"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["authorDisplayName"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["textDisplay"], existing_comment["Comment_History"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["likeCount"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["publishedAt"], response["items"][0]["replies"]["comments"][comment_index-1]["snippet"]["updatedAt"], False)
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
                new_comments.append(add_comment(comment["snippet"]["authorChannelId"]["value"], comment["id"], comment["snippet"]["authorDisplayName"], comment["snippet"]["textDisplay"], [], comment["snippet"]["likeCount"], comment["snippet"]["publishedAt"], comment["snippet"]["updatedAt"], False))
        
        # Print the categorized comments
        for comment in new_comments:
            print("New Comment:")
            print(comment)
        
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
            'UpdateDate': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["updatedAt"],
            'Deleted': False
        }
        
        comments.append(op_comment)
        
        # Extract reply comments information
        replies = response["items"][0]["replies"]["comments"]
        for reply in replies:
            reply_comment = {
                'ChannelID': reply["snippet"]["authorChannelId"]["value"],
                'CommentID': reply["id"],
                'Username': reply["snippet"]["authorDisplayName"], 
                'Comment': reply["snippet"]["textDisplay"],	
                'Comment_History': [],
                'Likes': reply["snippet"]["likeCount"],
                'PostDate': reply["snippet"]["publishedAt"],
                'UpdateDate': reply["snippet"]["updatedAt"],
                'Deleted': False
            }
            comments.append(reply_comment)
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
     
    conn.commit()
    return comments

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
    

if __name__ == "__main__":
    api_response = api_retrieve_thread("")
    json_object = json.dumps(api_response, indent = 4) 
    with open('api.json', 'w') as f:
        f.write(json_object)
    comments = process_and_save_data(api_response)
    # Print the recreated comments variable
    #print(comments)
    # Close the cursor and the connection
    cur.close()
    conn.close()

    
# Thread ID
# object►items►0►id
# Video ID
# object►items►0►snippet►videoId

# OP Username
# object►items►0►snippet►topLevelComment►snippet►authorDisplayName
# OP Channel ID
# object►items►0►snippet►topLevelComment►snippet►authorChannelId►value
# OP Comment
# object►items►0►snippet►topLevelComment►snippet►textDisplay
# OP post date
# object►items►0►snippet►topLevelComment►snippet►publishedAt
# OP update post date
# object►items►0►snippet►topLevelComment►snippet►updatedAt
# OP post likes
# object►items►0►snippet►topLevelComment►snippet►likeCount
# OP post comment ID
# object►items►0►snippet►topLevelComment►id

# Reply Username
# object►items►0►replies►comments►0►snippet►authorDisplayName
# Reply Channel ID
# object►items►0►replies►comments►0►snippet►authorChannelId►value
# Reply Comment
# object►items►0►replies►comments►0►snippet►textDisplay
# Reply post date
# object►items►0►replies►comments►0►snippet►publishedAt
# Reply update post date
# object►items►0►replies►comments►0►snippet►updatedAt
# Reply post likes
# object►items►0►replies►comments►0►snippet►likeCount
# Reply post comment ID
# object►items►0►replies►comments►0►id




#    json_object = json.dumps(response, indent = 4) 
#    with open('api.json', 'w') as f:
#        f.write(json_object)
#    print(json_object)
#    print(response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"])
#    replies = response["items"][0]["replies"]["comments"]
#    for i, reply in enumerate(replies):
#        print(f"{reply['snippet']['textDisplay']}")



