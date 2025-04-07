import sys
from datetime import datetime
from classes import Topic,Conf, Post



def filter_by_prefix(myTopicList, prefix):
    """
    Filter a list of strings to return only those that begin with a specific prefix.
    
    Args:
        myTopicList: A list of strings to filter
        prefix: A string to match against the beginning of each item
        
    Returns:
        A new list containing only the items that begin with the prefix
    """
    return [item for item in myTopicList if item.startswith(prefix)]



def wait_for_spacebar():
    print("Press spacebar to continue...")
    while True:
        if sys.stdin.read(1) == ' ':
            break

# check for -test switch on the command line        
def checkTest():
   
   # legacy implementation - use checkArg instead for new arg checks
    return checkArg("-test")
    

def checkArg(arg):
    # Checks if the command-line arguments contain the specified argument.
    
    
    for arg_item in sys.argv:
        if isinstance(arg_item, str):
            if arg in arg_item.split():
                return True
    return False

def conf_topic_post(handle):
    # handle is in the form of conf.topic.post or conf.ind.topic.post
    
    tokens = handle.split(".")
    if len(tokens) ==3:
        return tokens[0], tokens[1], tokens[2]
    elif len(tokens) == 4:
        return tokens[0] + "." + tokens[1], tokens[2], tokens[3]
    else:
        return None, None, None

def conffromhandle(handle):

    tokens = handle.split(".")
    
    
    if len(tokens) == 2:
        conf = tokens[0]
        return conf
    elif len(tokens) == 3:
        conf = tokens[0] + "." + tokens[1]
        return conf
    else:
        return None

def topicfromhandle(handle):
    tokens = handle.split(".")
    if len(tokens) > 1:
        return tokens[1]
    else:
        return None

def welldate_iso8601(date_str):
    # Strip any leading/trailing whitespace
    date_str = date_str.strip()
    
    # Parse the date string using datetime
    try:
        dt = datetime.strptime(date_str, "%a %d %b %y %H:%M")
    except ValueError:
        print("Error parsing date string in utils.py: " + date_str)
        dt = datetime.now()


    
    # Convert to ISO 8601 format

    returnValue= dt.isoformat()
    return returnValue

def nop():
    return

def find_topic_by_handle(myTopicObjectsList, handle):
    """
    Search a list of Topic objects for a match with a specific handle.
    
    Args:
        myTopicObjectsList: A list of Topic objects to search
        handle: A string to match against the handle field of each Topic object
        
    Returns:
        True if a match is found, False otherwise
    """
    for topic in myTopicObjectsList:
        if hasattr(topic, 'handle') and topic.handle == handle:
            return True
    return False