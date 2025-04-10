import sys
import utils
import json
from classes import Post, Topic, Conf




def makeObjects(input_text, conflist, topics):
    try:
        # Validate input parameters
        if not isinstance(input_text, str): 
            raise ValueError("input_text must be a string")
        if not isinstance(conflist, list):
            raise ValueError("conflist must be a list")
        topic_dict = {}

        # create list of older topics from 'topics'
        if len(topics) > 0:
            # add final newline to make split work correctly on last line of text
            topics = topics + "\n"
            # Split into lines, preserving leading whitespace for indented lines
            topic_list = topics.splitlines()
            
            # Filter out empty or whitespace-only strings and lines that begin with whitespace
            topic_list = [line for line in topic_list if line.strip() and (len(line) == 0 or not line[0].isspace())]
            
            # Process the list two lines at a time to create Topic objects
            i = 0

            conf_topic_list = []  # List of tuples with confname and topiclist
            while i < len(topic_list) - 1:  # Ensure we have at least two lines to process
                # Get the A line (first line) and B line (second line)
                line_a = topic_list[i]
                line_b = topic_list[i + 1]
                
                # Extract handle from line A (first token with : removed)
                handle = line_a.split(':')[0].strip()
                
                # Get conf from handle
                conf = utils.conffromhandle(handle)
                currentconf = conf

                # Get title from line A (rest of the line after handle and :)
                title = line_a.split(':', 1)[1].strip() if ':' in line_a else ""
                
                # Get date string from line B (last five tokens concatenated with spaces)
                tokens_b = line_b.split()
                if len(tokens_b) >= 5:
                    date_str = ' '.join(tokens_b[-5:])
                else:
                    date_str = line_b  # Fallback if not enough tokens
                
                # Convert date string to ISO8601 format
                lastUpdateISO8601 = utils.welldate_iso8601(date_str)
                
                # Create Topic object
                new_topic = Topic(conf, handle, title, lastUpdateISO8601)
                
                # Add topic to conf_topic_list
                found = False
                for conf_tuple in conf_topic_list:
                    if conf_tuple['confname'] == conf:
                        conf_tuple['topiclist'].append(new_topic)
                        found = True
                        break
                if not found:
                    conf_topic_list.append({'confname': conf, 'topiclist': [new_topic]})
                
                # Move to next pair of lines
                i += 2
        
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
                    currentconf.newTopicCount += 1
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

                    # update topic lastUpdateISO8601 if new post is newer
                    if (currenttopic.lastUpdateISO8601 <= newPost.datetime_iso8601):
                        currenttopic.lastUpdateISO8601 = newPost.datetime_iso8601

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
        
        
        if len(conflist) > 0:
            for testconf in conflist:
                if not isinstance(testconf, str):
                    continue
                # Check if testconf matches the beginning of any conference name in the confs list
                if not any(conf.name.startswith(testconf) for conf in confs):
                    newconf = Conf.create_empty()
                    newconf.name = testconf
                    newconf.handle = testconf
                    newconf.newTopicCount = 0
                    newconf.topics = []  # Initialize empty topic list
                    confs.append(newconf)
        
            # Merge topics from conf_topic_list into confs
            for conf in confs:
                for conf_tuple in conf_topic_list:
                    if conf_tuple['confname'].startswith(conf.name):
                        existing_handles = {topic.handle for topic in conf.topics}
                        for topic in conf_tuple['topiclist']:
                            if topic.handle not in existing_handles:
                                conf.topics.append(topic)
        
        # sort topic lists in confs
        for conf in confs:
            conf.topics.sort(key=lambda x: x.lastUpdateISO8601, reverse=True)
            
        
        
        print("Conference contents:")
        for conf in confs:
            print(f"\nConference: {conf.name}")
            print("Topics:")
            for topic in conf.topics:
                print(f"  - {topic.handle}: {topic.title}")
                print(f"    Last Update: {topic.lastUpdateISO8601}")

        # Process conflist
        

        # create json output with error handling
        try:
            json_output = json.dumps([conf.to_dict() for conf in confs], indent=2)
            return json_output
        except Exception as e:
            return json.dumps({"error": f"Error creating JSON output: {str(e)}"})
            
    except Exception as e:
        return json.dumps({"error": f"General error in makeObjects: {str(e)}"})


    