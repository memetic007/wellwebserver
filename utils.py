import sys
from datetime import datetime

# check for -test switch on the command line 

def wait_for_spacebar():
    print("Press spacebar to continue...")
    while True:
        if sys.stdin.read(1) == ' ':
            break
        
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

def conffromhandle(handle):

    tokens = handle.split(".")
    
    
    if len(tokens) > 1:
        conf = tokens[0]
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
    dt = datetime.strptime(date_str, "%a %d %b %y %H:%M")
    
    # Convert to ISO 8601 format

    returnValue= dt.isoformat()
    return returnValue

def nop():
    return