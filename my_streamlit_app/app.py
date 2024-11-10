import streamlit as st
import openai
from bs4 import BeautifulSoup
import requests
from PIL import Image
from io import BytesIO
import json


# Streamlit interface
st.title("Instagram Post Analyzer and Image Generator")

# Input field for OpenAI API key
openai_api_key = st.text_input("OpenAI API Key", type="password")
st.caption("We do not store your OpenAI API key. Paste it here to power the chatbot. [Get your OpenAI API key](https://platform.openai.com/account/api-keys)")

# Ensure the API key is provided
if not openai_api_key:
    st.warning("Please enter your OpenAI API key to proceed.")
    st.stop()

# Set the OpenAI API key
openai.api_key = openai_api_key

# Function to fetch Instagram content
def get_instagram_post_content(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        meta_tag_caption = soup.find('meta', property='og:description')
        caption = meta_tag_caption['content'] if meta_tag_caption else "Caption not found"
        meta_tag_image = soup.find('meta', property='og:image')
        image_url = meta_tag_image['content'] if meta_tag_image else None
        return caption, image_url
    except Exception as e:
        st.error(f"Error fetching Instagram post: {e}")
        return None, None

# Function to download the image
def download_image(image_url):
    try:
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        st.error(f"Error downloading image: {e}")
        return None

# Function to analyze the post and generate a product listing and DALL·E prompt
def analyze_post_and_generate_prompt(caption):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system", 
                    "content": "You generate a product listing in JSON format based on the input text and also create a concise prompt for DALL·E to create an image of the product."
                },
                {
                    "role": "user", 
                    "content": f"This is a product advertised on Instagram with the following caption: '{caption}'."
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "product_listing_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "product_name": {
                                "description": "The name of the product",
                                "type": "string"
                            },
                            "description": {
                                "description": "A brief description of the product",
                                "type": "string"
                            },
                            "features": {
                                "description": "Key features of the product",
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "price": {
                                "description": "The price of the product",
                                "type": "string"
                            },
                            "image_prompt": {
                                "description": "A concise prompt to generate an image of the product using DALL·E",
                                "type": "string"
                            }
                        },
                        "required": ["product_name", "description", "features", "image_prompt"],
                        "additionalProperties": False
                    }
                }
            }
        )
        content = response.choices[0].message.content
        return json.loads(content)  # Return the full JSON response
    except Exception as e:
        st.error(f"Error analyzing post and generating product listing: {e}")
        return None


# Function to generate an image
def generate_image(prompt):
    try:
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response.data[0].url
        return image_url
    except Exception as e:
        st.error(f"Error generating image: {e}")
        return None

# Initialize session state variables
if 'product_listing' not in st.session_state:
    st.session_state.product_listing = None
if 'dalle_prompt' not in st.session_state:
    st.session_state.dalle_prompt = None
if 'generated_image_url' not in st.session_state:
    st.session_state.generated_image_url = None

# Input field for Instagram post URL
url = st.text_input("Enter Instagram Post URL:")

if st.button("Analyze and Generate Product Listing"):
    if url:
        caption, image_url = get_instagram_post_content(url)
        if caption and image_url:
            st.subheader("Caption:")
            st.write(caption)
            
            st.subheader("Original Image:")
            img = download_image(image_url)
            if img:
                st.image(img, caption='Instagram Image', use_column_width=True)

            # Analyze post and generate product listing and DALL·E prompt
            product_listing = analyze_post_and_generate_prompt(caption)
            if product_listing:
                st.session_state.product_listing = product_listing
                st.session_state.dalle_prompt = product_listing.get("image_prompt")
                st.subheader("Product Listing JSON:")
                st.json(product_listing)

                st.subheader("DALL·E Prompt:")
                st.text_area("Prompt for Image Generation (read-only):", value=st.session_state.dalle_prompt, height=100)
        else:
            st.error("Failed to retrieve caption or image.")
    else:
        st.error("Please enter a valid Instagram post URL.")

# Display the DALL·E prompt and allow image generation if available
if st.session_state.dalle_prompt:
    if st.button("Generate Image from DALL·E Prompt"):
        st.session_state.generated_image_url = generate_image(st.session_state.dalle_prompt)

# Display the generated image if it has been created
if st.session_state.generated_image_url:
    st.subheader("Generated Image:")
    st.image(st.session_state.generated_image_url, caption='Generated by DALL·E 3', use_column_width=True)