import sys
import json
import utils

# check for -test switch on the command line 

    
# get userbane froim postheader
def getTitle(text):
    if ":" in text:
        return text.split(":", 1)[1].strip()  # Split at the first colon and strip whitespace
    return ""

def getUsername(s):
    """
    Extracts the substring between the last occurrence of '(' and ')'.
    Returns an empty string if no such pair exists.

    :param s: The input string.
    :return: The substring inside the last pair of parentheses or an empty string.
    """
    end = s.rfind(')')  # Find last ')'
    if end == -1:
        return ""  # No closing parenthesis found

    start = s.rfind('(', 0, end)  # Find last '(' before the last ')'
    if start == -1:
        return ""  # No opening parenthesis found

    return s[start + 1:end]  # Extract substring between '(' and ')'

# extract pseud from post header
def getPseud(s):
    """
    Extracts the substring between the first occurrence of ':' and '('.
    Strips leading and trailing whitespace. Returns an empty string if no valid match is found.

    :param s: The input string.
    :return: The extracted and trimmed substring or an empty string.
    """
    start = s.find(':')  # Find first ':'
    if start == -1:
        return ""  # No ':' found

    end = s.find('(', start)  # Find first '(' after ':'
    if end == -1:
        return ""  # No '(' found

    return s[start + 1:end].strip()  # Extract and strip space

# get time and date from post header
def getDateFromTopicHeader(arr):
    """
    Returns exactly the last five non-empty strings from the given list, joined with a single space.
    If there are fewer than five elements, it pads with empty strings.

    :param arr: The input list of strings.
    :return: A single string with non-empty elements separated by a space.
    """
    # Ensure we have at least 5 elements by padding
    padded_list = ([""] * 5 + arr)[-5:]
    
    # Filter out empty strings and join with a space
    return " ".join(filter(lambda x: len(x) > 0, padded_list))

# main program
# Read input from teststring.txt

if utils.checkTest():
    with open("teststring.txt", "r", encoding="utf-8", errors="replace") as file:
        input_text = file.read().strip()

        
        # add final newline to make split work correctly on last line of text
        input_text = input_text + "\n"

        # escape quotes in lines for later json purposes
        input_text = input_text.replace('"', '\\"')
else:
    # Read input and decode with error handling
    input_text = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
    
    # add final newline to make split work correctly on last line of text
    input_text = input_text + "\n"

    # escape quotes in lines for later json purposes
    input_text = input_text.replace('"', '\\"')

# Split into lines, preserving leading whitespace for indented lines
lines = input_text.splitlines()
  

# Create JSON entries and working values
entries = []
current_handle = "startupHandleError"
current_topic = "topicError"
current_datetime = ""
current_username = ""
current_title = ""
ignorelineflag = True
for line in lines:
        
    line = line.rstrip()  # Remove trailing whitespace
    
    # If line doesn't start with whitespace, check for handle
    if line and not line[0].isspace():
        tokens = line.split()
        if len(tokens) > 0:
            current_handle = tokens[0].replace(':', '')    
        else:
            current_handle = "headerHandleError"
        
        if current_handle.count('.') == 1:
            dictType = "topicheader"
            dictTimeDate = ""
            current_username = ""
            current_pseud = ""
            current_topic = current_handle
            current_title = getTitle(line)

        elif current_handle.count('.') == 2:
            dictType = "postheader"
            dictTimeDate = getDateFromTopicHeader(tokens)   
            current_datetime = dictTimeDate
            current_username = getUsername(line)
            current_pseud = getPseud(line)  
        else:
            dictType = "headerTypeError"
            dictTimeDate = ""

        dictHandle = current_handle
        dictTopic = current_topic 
        dictTitle = current_title
        dictUsername = current_username
        dictPseud = current_pseud
        dictText = line
    else:
        dictType = "posttext"
        dictHandle = current_handle
        dictTopic = ""
        dictTitle = ""
        dictUsername = ""
        dictPseud = ""
        dictText = line.strip()
        dictTimeDate = ""


    # ignore links information for topics   
    
    if not (current_handle.count('.') == 1 and dictType == "posttext"):
        
        # Append line data to list as dictionary
        entries.append({
            "type": dictType,
            "handle": current_handle,
            "topic": dictTopic,
            "title": dictTitle,
            "username": dictUsername,
            "pseud": dictPseud,
            "datetime": dictTimeDate,
            "text": dictText,
            
        })

# Format JSON with proper indentation
json_output = json.dumps(entries, indent=2)

# Print JSON output, ensuring UTF-8 encoding
sys.stdout.buffer.write(json_output.encode("utf-8", errors="replace"))

# Write to file if -text switch is present for testing
if utils.checkTest():
    with open("stringtestout.txt", "w", encoding="utf-8") as file:
        file.write(json_output) 
