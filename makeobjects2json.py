import sys
import utils
import json
from classes import Post, Topic, Conf


def makeObjects(input_text):
    
    # Parse the input text as JSON
    lines = []
    try:
        lines = json.loads(input_text)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        sys.exit(1)


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

    json_output = json.dumps([conf.to_dict() for conf in confs], indent=2)
    return json_output


    