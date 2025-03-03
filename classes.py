class Post:
    def __init__(self, handle, datetime, username, pseud, text=None):
        self.handle = handle
        self.datetime = datetime
        self.datetime_iso8601 = ""  # Initialize as empty string
        self.username = username
        self.pseud = pseud
        self.text = text if text is not None else []

    @classmethod
    def create_empty(cls):
        return cls("", "", "", "", [])

    def append_text(self, new_text):
        if isinstance(new_text, str):
            self.text.append(new_text)
        else:
            raise ValueError("Only strings can be appended to the text list.")

    def to_dict(self):
        return {
            "handle": self.handle,
            "datetime": self.datetime,
            "datetime_iso8601": self.datetime_iso8601,
            "username": self.username,
            "pseud": self.pseud,
            "text": self.text
        }

class Topic:
    def __init__(self, conf, handle, title, posts=None):
        self.conf = conf
        self.handle = handle
        self.title = title
        self.posts = posts if posts is not None else []

    def add_post(self, post):
        if isinstance(post, Post):
            self.posts.append(post)
        else:
            raise ValueError("Only Post objects can be added to the posts list.")

    @classmethod
    def create_empty(cls):
        return cls("", "", "", [])

    def to_dict(self):
        return {
            "conf": self.conf,
            "handle": self.handle,
            "title": self.title,
            "posts": [post.to_dict() for post in self.posts]
        }

class Conf:
    def __init__(self, name, handle, title, topics=None):
        self.handle = handle
        self.title = title
        self.topics = topics if topics is not None else []

    def add_topic(self, topic):
        if isinstance(topic, Topic):
            self.topics.append(topic)
        else:
            raise ValueError("Only Topic objects can be added to the topics list.")

    @classmethod
    def create_empty(cls):
        return cls("", "", "", [])

    def to_dict(self):
        return {
            "name": self.name,
            "handle": self.handle,
            "title": self.title,
            "topics": [topic.to_dict() for topic in self.topics]
        }