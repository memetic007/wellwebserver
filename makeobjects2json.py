import sys
import utils
import json
from classes import Post, Topic, Conf


if utils.checkTest():
    #with open("linejson.txt", "r", encoding="utf-8", errors="replace") as file:
    with open("linejson.txt", "rb") as file:  # Open in binary mode
        input_text = file.read()
    # Decode the UTF-16 bytes to a string
    # not sure how it came to be a UTF-16 file
    decoded_string = input_text.decode('utf-16', errors='replace')

    # Encode the string to UTF-8 bytes
    input_text = decoded_string.encode('utf-8', errors='replace')

else:
    # Read input and decode with error handling
    input_text = sys.stdin.buffer.read().strip()



# Parse the input text as JSON
lines = []
try:
    lines = json.loads(input_text)
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    sys.exit(1)

if not utils.checkArg("-conf"):

    #create list of topics
    topics = []
    currenttitle = ""
    currenttopic = Topic.create_empty()
    currentpost = Post.create_empty()
    for line in lines:
        if line['type'] == 'topicheader':
            newTopic = Topic.create_empty()
            newTopic.conf = utils.conffromhandle(line['handle'])
            newTopic.handle = line['handle']
            newTopic.title = line['title']
            topics.append(newTopic)
            currenttopic = newTopic
        elif line['type'] == 'postheader':
            newPost = Post.create_empty()
            newPost.handle = line['handle']
            newPost.datetime = line['datetime']
            newPost.datetime_iso8601 = utils.welldate_iso8601(newPost.datetime)
            newPost.username = line['username']
            newPost.pseud = line['pseud']
            newPost.text = []
            currenttopic.add_post(newPost)
            currentpost = newPost

        elif line['type'] == 'posttext':
            currentpost.append_text(line['text'])
        else:
            print(f"Unknown line type: {line['type']}") 
else:
    # create list of confs
    confs = []
    topics = []
    previousconfname = ""
    currenttitle = ""
    currentconf = Conf.create_empty()
    currenttopic = Topic.create_empty()
    currentpost = Post.create_empty()
    for line in lines:
        if line['type'] == 'topicheader':
            newTopic = Topic.create_empty()
            newTopic.conf = utils.conffromhandle(line['handle'])
            if previousconfname != newTopic.conf:
                currentconf = Conf.create_empty()
                previousconfname = newTopic.conf
                confs.append(currentconf)
                currentconf.name = newTopic.conf
                currentconf.handle = currentconf.name

            currentconf.add_topic(newTopic)

            newTopic.handle = line['handle']
            newTopic.title = line['title']
            topics.append(newTopic)
            
            currenttopic = newTopic

        elif line['type'] == 'postheader':
            newPost = Post.create_empty()
            newPost.handle = line['handle']
            newPost.datetime = line['datetime']
            newPost.datetime_iso8601 = utils.welldate_iso8601(newPost.datetime)
            newPost.username = line['username']
            newPost.pseud = line['pseud']
            newPost.text = []
            currenttopic.add_post(newPost)
            currentpost = newPost

        elif line['type'] == 'posttext':
            currentpost.append_text(line['text'])
        else:
            print(f"Unknown line type: {line['type']}")    
    # create json output
    


# Format JSON with proper indentation

if utils.checkArg("-conf"):
    json_output = json.dumps([conf.to_dict() for conf in confs], indent=2)
else:
    json_output = json.dumps([topic.to_dict() for topic in topics], indent=2)

# Print JSON output, ensuring UTF-8 encoding
sys.stdout.buffer.write(json_output.encode("utf-8", errors="replace"))


# Write to file if -text switch is present for testing
if utils.checkTest():
    with open("makeobjectsout.txt", "w", encoding="utf-8") as file:
        file.write(json_output) 