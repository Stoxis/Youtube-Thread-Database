# -*- coding: utf-8 -*-

# Sample Python code for youtube.commentThreads.list
# See instructions for running these code samples locally:
# https://developers.google.com/explorer-help/code-samples#python

import os
import psycopg2
import json
import googleapiclient.discovery

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
        api_service_name, api_version, developerKey = DEVELOPER_KEY)

    request = youtube.commentThreads().list(
        part="snippet,replies",
        id=id
    )
    response = request.execute()
    return response

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
    
    
    # Check if the thread exists in the database
    
    if existing_thread is not None:
        new_comments = []
        edited_comments = []
        # Thread already exists in the database
        # Perform actions for an existing thread
        print("Existing thread actions")
        existing_comments = existing_thread[0]
        # Loop through response and check for new, new edited, deleted, or old edited comments
        for response_comment in response:
            response_comment_id = response_comment['CommentID']
            response_comment_text = response_comment['Comment']
        
            # Check if response comment ID exists in existing_comments
            matching_comment = None
            for existing_comment in existing_comments:
                existing_comment_id = existing_comment['CommentID']
                existing_comment_text = existing_comment['Comment']
        
                if response_comment_id == existing_comment_id:
                    matching_comment = existing_comment
                    break
        
            if matching_comment is None:
                # Response comment ID doesn't exist in existing_comments == new
                print("New comment:", response_comment_text)
            elif response_comment_text != matching_comment['Comment']:
                # Response comment doesn't match message in existing_comments but ID is the same == new edited
                print("New edited comment:", response_comment_text)
            else:
                # Comment exists in existing_comments
                print("Existing comment:", response_comment_text)
        
        
        # Loop through existing_comments and check for deleted or old edited comments
        for existing_comment in existing_comments:
            existing_comment_id = existing_comment['CommentID']
            existing_comment_text = existing_comment['Comment']
        
            # Check if existing comment ID exists in response
            matching_comment = None
            for response_comment in response:
                response_comment_id = response_comment['CommentID']
                response_comment_text = response_comment['Comment']
        
                if existing_comment_id == response_comment_id:
                    matching_comment = response_comment
                    break
        
            if matching_comment is None:
                # Existing comment ID doesn't exist in response == deleted
                print("Deleted comment:", existing_comment_text)
            elif existing_comment_text != matching_comment['Comment']:
                # Existing comment doesn't match message in response but ID is the same == old edited
                print("Old edited comment:", existing_comment_text)
        print(existing_thread[0][0]['Likes'])
        print("\n\n")
    else:
        comments = []
        # Thread does not exist in the database
        # Perform actions for a new thread
        print("New thread actions")
        # Extract OP comment information
        
        op_comment = {
            'ChannelID': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorChannelId"]["value"],
            'CommentID': response["items"][0]["snippet"]["topLevelComment"]["id"],
            'Username': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"],
            'Comment': response["items"][0]["snippet"]["topLevelComment"]["snippet"]["textDisplay"],
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
                'Likes': reply["snippet"]["likeCount"],
                'PostDate': reply["snippet"]["publishedAt"],
                'UpdateDate': reply["snippet"]["updatedAt"],
                'Deleted': False
            }
            comments.append(reply_comment)
        channelIDs = set(comment['ChannelID'] for comment in comments)
        comments_json = json.dumps(comments)
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

if __name__ == "__main__":
    api_response = api_retrieve_thread("")
    comments = process_and_save_data(api_response)
    # Print the recreated comments variable
    print(comments)
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



