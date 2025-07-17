# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT
from requests import get
from app.models.post import Post

posts_json_url = "http://127.0.0.1:4000/assets/data/posts.json"

def process_site_posts():
    """Process the posts from the website and send them as an email newsletter."""
    
    # Fetch posts from the JSON URL
    response = get(posts_json_url)
    if response.status_code != 200:
        return {"error": "Failed to fetch posts"}, response.status_code
    
    data = response.json()
    if not data:
        return {"error": "No posts found"}, 404

    # Convert raw data to Post objects
    posts = [Post(post) for post in data]
    for post in posts:
        print(f"Processing post: {post.title} by {post.author} ({post})")

    

    return {"status": "success", "posts_processed": len(posts)}

if __name__ == "__main__":
    print(process_site_posts())