# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
from typing import Dict, Any
class Post:
    """Represents a blog post, as defined by the Jekyll data structure."""
    raw: dict # not recommended to use directly, use properties instead

    output: str
    content: str
    collection: str
    name: str
    path: str
    url: str
    _id: str
    next_post: Dict[str, Any] | None
    categories: list
    excerpt: str
    relative_path: str
    date: str
    title: str
    tags: list
    previous_post: Dict[str, Any] | None
    draft: bool
    author: str
    layout: str
    ministry: str
    slug: str
    ext: str

    def __init__(self, raw_data: dict):
        self.raw = raw_data
        self.output = raw_data.get("output", "")
        self.content = raw_data.get("content", "")
        self.collection = raw_data.get("collection", "")
        self.name = raw_data.get("name", "")
        self.path = raw_data.get("path", "")
        self.url = raw_data.get("url", "")
        self._id = raw_data.get("id", "")
        self.next_post = raw_data.get("next", None)
        self.categories = raw_data.get("categories", [])
        self.excerpt = raw_data.get("excerpt", "")
        self.relative_path = raw_data.get("relative_path", "")
        self.date = raw_data.get("date", "")
        self.title = raw_data.get("title", "")
        self.tags = raw_data.get("tags", [])
        self.previous_post = raw_data.get("previous", None)
        self.draft = raw_data.get("draft", False)
        self.author = raw_data.get("author", "")
        self.layout = raw_data.get("layout", "")
        self.ministry = raw_data.get("ministry", "")
        self.slug = raw_data.get("slug", "")
        self.ext = raw_data.get("ext", "")

    def __repr__(self):
        raw_bytes = len(str(self.raw).encode('utf-8'))
        return f"<Post title=\"{self.title}\" date=\"{self.date}\" author=\"{self.author}\", rawBytes={raw_bytes}>"
