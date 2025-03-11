import sys
import utils
import json
from classes import Post, Topic, Conf


def makeObjects(input_text, conflist):
    try:
        # Validate input parameters
        if not isinstance(input_text, str):
            raise ValueError("input_text must be a string")
        if not isinstance(conflist, list):
            raise ValueError("conflist must be a list")
            
        # Parse the input text as JSON
        lines = []
        try:
            lines = json.loads(input_text)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON format: {str(e)}"})
        
        if not isinstance(lines, list):
            return json.dumps({"error": "JSON data must be a list"})

        # create list of confs
        confs = []
        topics = []
        previousconfname = ""
        currenttitle = ""
        currentconf = Conf.create_empty()
        currenttopic = Topic.create_empty()
        currentpost = Post.create_empty()
        
        for line in lines:
            try:
                # Validate line structure
                if not isinstance(line, dict):
                    continue
                if 'type' not in line:
                    continue
                    
                if line['type'] == 'topicheader':
                    if 'handle' not in line:
                        continue
                        
                    newTopic = Topic.create_empty()
                    newTopic.conf = utils.conffromhandle(line['handle'])
                    if not newTopic.conf:  # Check if conf is None or empty
                        continue
                        
                    if previousconfname != newTopic.conf:
                        currentconf = Conf.create_empty()
                        previousconfname = newTopic.conf
                        confs.append(currentconf)
                        currentconf.name = newTopic.conf
                        currentconf.handle = currentconf.name

                    currentconf.add_topic(newTopic)

                    newTopic.handle = line['handle']
                    newTopic.title = line.get('title', '')  # Use get() with default value
                    topics.append(newTopic)
                    
                    currenttopic = newTopic

                elif line['type'] == 'postheader':
                    if 'handle' not in line:
                        continue
                        
                    newPost = Post.create_empty()
                    newPost.handle = line['handle']
                    newPost.datetime = line.get('datetime', '')
                    newPost.datetime_iso8601 = utils.welldate_iso8601(newPost.datetime) if newPost.datetime else ''
                    newPost.username = line.get('username', '')
                    newPost.pseud = line.get('pseud', '')
                    newPost.text = []
                    currenttopic.add_post(newPost)
                    currentpost = newPost

                elif line['type'] == 'posttext':
                    if currentpost and 'text' in line:
                        currentpost.append_text(line['text'])
                else:
                    print(f"Unknown line type: {line['type']}")
                    
            except Exception as e:
                print(f"Error processing line: {str(e)}")
                continue
        
        # Process conflist
        if len(conflist) > 0:
            for testconf in conflist:
                if not isinstance(testconf, str):
                    continue
                # Check if testconf matches the beginning of any conference name in the confs list
                if not any(conf.name.startswith(testconf) for conf in confs):
                    newconf = Conf.create_empty()
                    newconf.name = testconf
                    newconf.handle = testconf
                    confs.append(newconf)

        # create json output with error handling
        try:
            json_output = json.dumps([conf.to_dict() for conf in confs], indent=2)
            return json_output
        except Exception as e:
            return json.dumps({"error": f"Error creating JSON output: {str(e)}"})
            
    except Exception as e:
        return json.dumps({"error": f"General error in makeObjects: {str(e)}"})


    