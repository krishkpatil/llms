import streamlit as st
import openai
from bs4 import BeautifulSoup
import requests
from PIL import Image, ImageOps
from io import BytesIO
import json
from rembg import remove  # Import rembg for background removal

# Streamlit interface
st.title("Instagram Post Analyzer and Image Generator with Image Editing")

# Sidebar
with st.sidebar:
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
        img = Image.open(BytesIO(response.content)).convert("RGBA")
        return img
    except Exception as e:
        st.error(f"Error downloading image: {e}")
        return None

# Function to remove background from image
def remove_background(img):
    try:
        output = remove(img)
        return output
    except Exception as e:
        st.error(f"Error removing background: {e}")
        return img  # Return original image if background removal fails

# Function to resize and pad image to be square
def make_image_square(img):
    try:
        # Calculate new size and padding
        max_dim = max(img.size)
        new_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        new_img.paste(img, ((max_dim - img.size[0]) // 2, (max_dim - img.size[1]) // 2))
        new_img = new_img.resize((1024, 1024))
        return new_img
    except Exception as e:
        st.error(f"Error making image square: {e}")
        return img

# Function to analyze the post and generate a product listing and DALL·E prompt
def analyze_post_and_generate_prompt(caption):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a prompt engineer. Based on the input text, you generate a product listing in JSON format, "
                        "and also create a concise DALL·E prompt to create a photorealistic image of the product that is as close as possible "
                        "to the original image from Instagram. The DALL·E prompt should include the brand name if any, and use the features from the analysis. "
                        "Ensure that the DALL·E prompt instructs to generate a photorealistic image."
                    )
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
                                "description": "A concise prompt to generate an image of one product with the context of the description of the product using DALL·E",
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
        # Extract JSON from the assistant's message
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        json_content = content[json_start:json_end]
        return json.loads(json_content)
    except Exception as e:
        st.error(f"Error analyzing post and generating product listing: {e}")
        return None

# Function to generate an image edit
def generate_image_edit(prompt, image, mask):
    try:
        # Ensure images are in PNG format and have the same dimensions
        image = image.convert("RGBA")
        mask = mask.convert("RGBA")

        # Make images square
        image = make_image_square(image)
        mask = make_image_square(mask)

        # Save images to bytes
        image_bytes = BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        mask_bytes = BytesIO()
        mask.save(mask_bytes, format='PNG')
        mask_bytes.seek(0)

        response = openai.images.edit(
            image=image_bytes,
            mask=mask_bytes,
            prompt=prompt,
            n=2,
            size="1024x1024"
        )
        image_url = response.data[0].url
        return image_url
    except Exception as e:
        st.error(f"Error generating image edit: {e}")
        return None

# Initialize session state variables
if 'caption' not in st.session_state:
    st.session_state.caption = None
if 'image_url' not in st.session_state:
    st.session_state.image_url = None
if 'product_listing' not in st.session_state:
    st.session_state.product_listing = None
if 'dalle_prompt' not in st.session_state:
    st.session_state.dalle_prompt = None
if 'generated_image_url' not in st.session_state:
    st.session_state.generated_image_url = None
if 'processed_image' not in st.session_state:
    st.session_state.processed_image = None
if 'original_image' not in st.session_state:
    st.session_state.original_image = None

# Input field for Instagram post URL
url = st.text_input("Enter Instagram Post URL (or leave blank to upload an image):")

# File uploader for image
uploaded_file = st.file_uploader("Or upload an image of the product:", type=["jpg", "jpeg", "png"])

# Input field for caption if uploading an image
if uploaded_file is not None:
    caption_input = st.text_area("Enter the product caption or description:")

if st.button("Analyze and Generate Product Listing"):
    if url:
        # Proceed with Instagram content
        caption, image_url = get_instagram_post_content(url)
        if caption and image_url:
            st.session_state.caption = caption
            st.session_state.image_url = image_url
            # Download the image
            img = download_image(image_url)
            if img:
                st.session_state.original_image = img
                # Remove background
                processed_img = remove_background(img)
                st.session_state.processed_image = processed_img
            else:
                st.error("Failed to download image.")
            # Analyze post and generate product listing and DALL·E prompt
            product_listing = analyze_post_and_generate_prompt(caption)
            if product_listing:
                st.session_state.product_listing = product_listing
                st.session_state.dalle_prompt = product_listing.get("image_prompt")
                st.session_state.generated_image_url = None  # Reset generated image
            else:
                st.error("Failed to generate product listing.")
        else:
            st.error("Failed to retrieve caption or image from Instagram.")
    elif uploaded_file is not None and caption_input:
        # Proceed with uploaded image and user-provided caption
        st.session_state.caption = caption_input
        # Load the uploaded image
        img = Image.open(uploaded_file).convert("RGBA")
        st.session_state.original_image = img
        # Remove background
        processed_img = remove_background(img)
        st.session_state.processed_image = processed_img
        # Analyze caption and generate product listing and DALL·E prompt
        product_listing = analyze_post_and_generate_prompt(caption_input)
        if product_listing:
            st.session_state.product_listing = product_listing
            st.session_state.dalle_prompt = product_listing.get("image_prompt")
            st.session_state.generated_image_url = None  # Reset generated image
        else:
            st.error("Failed to generate product listing.")
    else:
        st.error("Please enter a valid Instagram post URL or upload an image with a caption.")

# Display the caption if available
if st.session_state.caption:
    st.subheader("Caption:")
    st.write(st.session_state.caption)

# Display the original image in the sidebar
with st.sidebar:
    if st.session_state.image_url:
        st.subheader("Original Image:")
        st.image(st.session_state.original_image, caption='Instagram Image', use_container_width=True, output_format='auto')
    elif st.session_state.original_image:
        st.subheader("Uploaded Image:")
        st.image(st.session_state.original_image, caption='Uploaded Image', use_container_width=True)

# Display the product listing JSON and DALL·E prompt if available
if st.session_state.product_listing:
    st.subheader("Product Listing JSON:")
    st.json(st.session_state.product_listing)

# Display the processed image after analysis and before prompt generation
if st.session_state.processed_image:
    st.subheader("Processed Image (Background Removed):")
    st.image(st.session_state.processed_image, caption='Image with Background Removed', use_container_width=True)

# Make the DALL·E prompt editable
if st.session_state.dalle_prompt is not None:
    st.subheader("DALL·E Prompt:")
    # Editable text area for the prompt
    edited_prompt = st.text_area("Edit the prompt for image generation:", value=st.session_state.dalle_prompt, height=100)
    # Update the session state with the edited prompt
    st.session_state.dalle_prompt = edited_prompt

    # Button to generate image edit using the mask
    if st.button("Generate Image Edit with DALL·E"):
        if st.session_state.original_image and st.session_state.processed_image:
            st.session_state.generated_image_url = generate_image_edit(
                st.session_state.dalle_prompt,
                st.session_state.original_image,
                st.session_state.processed_image
            )
        else:
            st.error("Original image or mask not available.")
    # Optionally, you can still provide the option to generate a new image
    elif st.button("Generate New Image from DALL·E Prompt"):
        st.session_state.generated_image_url = generate_image(st.session_state.dalle_prompt)

# Display the generated image if it has been created
if st.session_state.generated_image_url:
    st.subheader("Generated Image:")
    st.image(st.session_state.generated_image_url, caption='Generated by DALL·E', use_container_width=True)
