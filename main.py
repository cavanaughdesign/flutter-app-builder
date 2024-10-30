import re
import subprocess
import logging
import pandas as pd  # Correct
import numpy as np
import streamlit as st
import openai
import zipfile
import io
import json
import os
import shutil
import hashlib
import pickle
import time
from swarm import Swarm, Agent
import tqdm  # Import Swarm framework

client = openai.OpenAI()


# Configuration and constants
CACHE_DIR = "flutter_app_cache"
CACHE_EXPIRATION = 24 * 60 * 60 
OPENAI_REQUEST_TIMEOUT = 60  # Timeout for OpenAI requests
PROCESS_TIMEOUT = 180        # Timeout for subprocess calls

# Set up logging
logging.basicConfig(filename='flutter_app_generator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_cache_key(instructions, mode, state_management, target_platform, database_type):
    key = f"{instructions}|{mode}|{state_management}|{','.join(sorted(target_platform))}|{database_type}"
    return hashlib.md5(key.encode()).hexdigest()

def get_cached_result(cache_key):
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < CACHE_EXPIRATION:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        else:
            os.remove(cache_file)
            logging.info(f"Removed expired cache file: {cache_file}")
    return None

def save_to_cache(cache_key, result):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
        with open(cache_file, "wb") as f:
            pickle.dump(result, f)
        logging.info(f"Saved result to cache: {cache_file}")
    except Exception as e:
        logging.error(f"Error saving to cache: {str(e)}")

def load_config():
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}")
    return {
        "openai_api_key": "",
        "output_folder": "generated_flutter_apps",
        "git_repo_url": "",
        "flutter_sdk_path": "C:/flutter/",
        "prompts": {
            "Full-Stack Developer": "You are a Full-Stack Developer. Create a Flutter app with both frontend and backend integration based on the following instructions:",
            "UI Designer": "You are a UI Designer. Create a Flutter app with a beautiful and intuitive user interface based on the following instructions:",
            "Mobile App Specialist": "You are a Mobile App Specialist. Create a Flutter app optimized for mobile devices with the following features:"
        }
    }

# Save configuration
def save_config(config):
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        logging.info("Config saved successfully")
    except Exception as e:
        logging.error(f"Error saving config: {str(e)}")

def validate_app_name(app_name):
    """Validates the app name using a regular expression."""
    if not re.match(r"^[a-z_]+$", app_name):
        raise ValueError("Invalid app name. Use lowercase letters and underscores only.")
    return app_name

def generate_flutter_project_structure(app_name, target_platform, flutter_sdk_path):
    """Generates the Flutter project structure."""
    try:
        temp_dir = f"temp_{app_name}"
        os.makedirs(temp_dir, exist_ok=True)
        create_command = [
            os.path.join(flutter_sdk_path, "bin", "flutter"),
            "create",
            f"--platforms={target_platform}",
            app_name
        ]
        subprocess.run(create_command, cwd=temp_dir, check=True, timeout=PROCESS_TIMEOUT)
        return os.path.join(temp_dir, app_name)
    except subprocess.TimeoutExpired as e:
        logging.error(f"Timeout creating Flutter project: {str(e)}")
        raise TimeoutError(f"Flutter project creation timed out after {PROCESS_TIMEOUT} seconds.") from e
    except subprocess.CalledProcessError as e:
        logging.error(f"Error creating Flutter project: {str(e)}, Output: {e.stderr.decode()}")
        raise RuntimeError(f"Error creating Flutter project: {e.stderr.decode()}") from e
    except Exception as e:
        logging.exception(f"Unexpected error creating Flutter project: {str(e)}")
        raise

def generate_flutter_app_code(instructions, mode, state_management, config):
    try:
        openai.api_key = config["openai_api_key"]
        prompt = (
            f"{config['prompts'][mode]}\n\n"
            f"Instructions:\n{instructions}\n\n"
            f"Requirements:\n"
            f"- Use {state_management} for state management.\n"
            f"- Follow Material Design 3 guidelines and best practices.\n"
            f"- Utilize Material Design 3 widgets.\n"
            f"- Ensure the code is modular and follows best practices.\n"
            f"- Include comments and documentation for clarity.\n"
            f"- Adhere to the latest Flutter guidelines.\n\n"
            f"Provide the complete content for the main.dart file."
        )
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant that generates Flutter app code."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            n=1,
            stop=None,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except openai.error.Timeout as e:
        logging.error(f"OpenAI API request timed out: {str(e)}")
        raise TimeoutError("The request to OpenAI timed out. Please try again later.") from e
    except Exception as e:
        logging.exception(f"Error generating Flutter app code: {str(e)}")
        raise

def generate_screens_and_widgets(instructions, app_name):
    try:
        prompt = (
            f"Generate comprehensive Flutter code for additional screens and widgets for the app '{app_name}' based on these instructions:\n\n"
            f"{instructions}\n\n"
            f"Requirements:\n"
            f"- Follow Material Design 3 guidelines and best practices.\n"
            f"- Utilize Material Design 3 widgets.\n"
            f"- Include navigation, state management, and UI components.\n"
            f"- Ensure the code is modular and follows best practices.\n"
            f"- Adhere to the latest Flutter guidelines."
        )
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant that generates perfect Flutter app code."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            n=1,
            stop=None,
            temperature=0.7,
        )
        # Accessing 'content' from the correct location in the response 
        return response.choices[0].message.content
    except openai.error.Timeout as e:
        logging.error(f"OpenAI API request timed out: {str(e)}")
        raise TimeoutError("The request to OpenAI timed out. Please try again later.") from e
    except Exception as e:
        logging.error(f"Error generating screens and widgets code: {str(e)}")
        raise

def generate_networking_code(instructions, app_name):
    prompt = (
        f"Generate comprehensive Flutter networking code for the app '{app_name}' based on these instructions:\n\n"
        f"{instructions}\n\n"
        f"Requirements:\n"
        f"- Follow Material Design 3 guidelines and best practices.\n"
        f"- Utilize Material Design 3 widgets where applicable.\n"
        f"- Include API client setup, HTTP request handling, error handling, and best practices for performance and security.\n"
        f"- Ensure the code is modular and follows the latest Flutter guidelines."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant that generates perfect Flutter app code."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2000,
        n=1,
        stop=None,
        temperature=0.7,
    )
    try:
        # Accessing 'content' from the correct location in the response 
        return response.choices[0].message.content
    except openai.error.Timeout as e:
        logging.error(f"OpenAI API request timed out: {str(e)}")
        raise TimeoutError("The request to OpenAI timed out. Please try again later.") from e
    except Exception as e:
        logging.error(f"Error accessing content from response: {str(e)}")
        raise

def generate_database_code(instructions, app_name, database_type):
    prompt = (
        f"Generate Flutter database code for the app '{app_name}' using {database_type} based on these instructions:\n\n"
        f"{instructions}\n\n"
        f"Requirements:\n"
        f"- Follow Material Design 3 guidelines and best practices.\n"
        f"- Utilize Material Design 3 widgets where applicable.\n"
        f"- Include setup, CRUD operations, and best practices for data handling and security.\n"
        f"- Ensure the code is optimized for performance and follows the latest Flutter and {database_type} guidelines."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant that generates perfect Flutter app code."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2000,
        n=1,
        stop=None,
        temperature=0.7,
    )
    try:
        # Accessing 'content' from the correct location in the response 
        return response.choices[0].message.content
    except openai.error.Timeout as e:
        logging.error(f"OpenAI API request timed out: {str(e)}")
        raise TimeoutError("The request to OpenAI timed out. Please try again later.") from e
    except Exception as e:
        logging.error(f"Error accessing content from response: {str(e)}")
        raise

def generate_authentication_code(instructions, app_name):
    prompt = (
        f"Generate Flutter authentication code for the app '{app_name}' based on these instructions:\n\n"
        f"{instructions}\n\n"
        f"Requirements:\n"
        f"- Follow Material Design 3 guidelines and best practices.\n"
        f"- Utilize Material Design 3 widgets where applicable.\n"
        f"- Include user registration, login, and logout functionalities.\n"
        f"- Ensure the code is secure and follows best practices for handling user credentials and authentication tokens."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant that generates perfect Flutter app code."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2000,
        n=1,
        stop=None,
        temperature=0.7,
    )
    try:
        # Accessing 'content' from the correct location in the response 
        return response.choices[0].message.content
    except openai.error.Timeout as e:
        logging.error(f"OpenAI API request timed out: {str(e)}")
        raise TimeoutError("The request to OpenAI timed out. Please try again later.") from e
    except Exception as e:
        logging.error(f"Error accessing content from response: {str(e)}")
        raise

# Create zip file
def create_zip_file(project_path):
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, _, files in os.walk(project_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, project_path)
                    zip_file.write(file_path, arcname)
        return zip_buffer.getvalue()
    except Exception as e:
        logging.error(f"Error creating zip file: {str(e)}")
        raise

# Initialize Git repository
def initialize_git_repo(project_path: str, git_repo_url: str) -> None:
    try:
        commands = [
            ["git", "init"],
            ["git", "add", "."],
            ["git", "commit", "-m", "Initial commit"],
            ["git", "branch", "-M", "main"],
            ["git", "remote", "add", "origin", git_repo_url],
            ["git", "push", "-u", "origin", "main"]
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Command {cmd} failed: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        
        logging.info(f"Git repository initialized and pushed to {git_repo_url}")
    except subprocess.CalledProcessError as e:
        # Log the specific Git error for debugging
        logging.error(f"Git command failed: {e.cmd}, Return code: {e.returncode}, "
                      f"Output: {e.stdout.decode()}, Error: {e.stderr.decode()}")
        # More informative error message for the user
        st.warning(f"Git initialization failed. "
                   f"Please check your repository URL and ensure you have push access. "
                   f"You can manually initialize the Git repository later.")
    except Exception as e:
        logging.exception(f"Unexpected error during Git initialization: {str(e)}")
        st.warning(f"An error occurred during Git initialization. "
                   f"You can manually initialize the Git repository later.")

# Define Swarm Agents for Code Review and Debugging
def setup_swarm():
    # Initialize Swarm without agents
    swarm = Swarm()
    
    # Define Code Review Agent with enhanced prompt
    code_review_agent = Agent(
        name="CodeReviewAgent",
        instructions=(
            "You are an expert code reviewer with extensive experience in Flutter development. "
            "Analyze the provided Flutter code thoroughly and suggest improvements. "
            "Your review should include clear explanations of the code, suggestions for enhancements,and best practices for Flutter development. "
            "Your review should cover code quality, adherence to best practices, performance optimization, "
            "readability, maintainability, and potential bugs. Provide detailed feedback and actionable suggestions."
        )
    )

    # Define Debugging Agent with enhanced prompt
    debugging_agent = Agent(
        name="DebuggingAgent",
        instructions=(
            "You are a skilled debugger with deep knowledge of Flutter and Dart. "
            "Identify and fix any issues in the provided Flutter code. "
            "Your debugging process should involve thorough analysis of the code,identification of logical errors, runtime issues, and potential crashes.  "
            "Your debugging should include finding logical errors, runtime issues, and potential crashes. "
            "Ensure the code is robust, efficient, and follows best practices. Provide detailed explanations of the fixes."
        )
    )
    
    return swarm, code_review_agent, debugging_agent

# Review and debug code using Swarm agents
def review_and_debug_code(swarm, code_review_agent, debugging_agent, code_content, filename):
    # Review Phase
    review_prompt = (
        f"Please review the following code in {filename} and suggest improvements. "
        f"Ensure that any placeholder or TODO functions are fully implemented:\n\n{code_content}"
    )
    review_response = swarm.run(agent=code_review_agent, messages=[{"role": "user", "content": review_prompt}])
    if not review_response.messages:
        logging.error(f"No response received from CodeReviewAgent for {filename}.")
        return code_content  # Return original if no response
    
    review_suggestion = review_response.messages[-1].content
    logging.info(f"Code review for {filename}: {review_suggestion}")

    # Debugging Phase
    debug_prompt = (
        f"Based on the following review, please debug the code in {filename}. "
        f"Ensure that any placeholder or TODO functions are fully implemented:\n\n"
        f"Review Feedback:\n{review_suggestion}\n\nCode:\n{code_content}"
    )
    debug_response = swarm.run(agent=debugging_agent, messages=[{"role": "user", "content": debug_prompt}])
    if not debug_response.messages:
        logging.error(f"No response received from DebuggingAgent for {filename}.")
        return review_suggestion  # Return review suggestion if no response
    
    debug_suggestion = debug_response.messages[-1].content
    logging.info(f"Debugging for {filename}: {debug_suggestion}")
    
    return debug_suggestion

# Main app
def main():
    st.set_page_config(page_title="FABS-Flutter App Builder with Swarm", layout="wide")
    st.title("FABS-Flutter App Builder with Swarm")
    st.subheader("Powered by OpenAI")
    st.markdown("**Engineered by Cavanaugh Design Studio**")

    config = load_config()

    # Setup Swarm and Agents
    swarm, code_review_agent, debugging_agent = setup_swarm()

    # Create two columns
    left_column, right_column = st.columns(2)

    with left_column:
        # Step 1: App Basics
        st.header("Step 1: App Basics")
        app_name = st.text_input("Enter your app name (use lowercase and underscores)", value="my_flutter_app")
        try:
            validated_app_name = validate_app_name(app_name) 
        except ValueError as e:
            st.error(str(e)) 
            return # Stop execution if validation fails

        # Step 2: Project Setup
        st.header("Step 2: Project Setup")
        mode = st.selectbox("Select App Mode", ["UI Designer", "Full-Stack Developer", "Mobile App Specialist"])
        state_management = st.selectbox("Choose State Management", ["Provider", "BLoC", "Riverpod"])
        target_platform = st.multiselect("Select Target Platforms", 
                                        ["android", "ios", "web", "windows", "macos", "linux"], 
                                        default=["android", "ios"])
        database_type = st.selectbox("Select Database (Optional)", ["None", "SQLite", "Firestore", "Hive"])

        # Step 3: App Instructions 
        st.header("Step 3: App Instructions")
        instructions = st.text_area("Provide Detailed Instructions for Your Flutter App")
         # Add file uploader for optional instructions upload
        uploaded_file = st.file_uploader("Or upload instructions file", type=["txt"])
        if uploaded_file is not None:
            try:
                instructions = uploaded_file.read().decode("utf-8")
                st.text_area("Provide Detailed Instructions for Your Flutter App", value=instructions)
            except Exception as e:
                st.error(f"Error reading uploaded file: {str(e)}")
            

    # Settings
    if st.sidebar.checkbox("Show Settings"):
        st.sidebar.subheader("Settings")
        config["openai_api_key"] = st.sidebar.text_input("OpenAI API Key", value=config["openai_api_key"], type="password")
        config["git_repo_url"] = st.sidebar.text_input("Git Repository URL", value=config["git_repo_url"])
        config["output_folder"] = st.sidebar.text_input("Output Folder", value=config["output_folder"])
        config["flutter_sdk_path"] = st.sidebar.text_input("Flutter SDK Path", value=config["flutter_sdk_path"])
        
        st.sidebar.subheader("Prompts")
        for key in config["prompts"]:
            config["prompts"][key] = st.sidebar.text_area(f"{key} Prompt", value=config["prompts"][key])
        
        # Add a button to clear the cache
        if st.sidebar.button("Clear Cache"):
            try:
                shutil.rmtree(CACHE_DIR)
                st.sidebar.success("Cache cleared successfully!")
            except Exception as e:
                st.sidebar.error(f"Error clearing cache: {str(e)}")

        if st.sidebar.button("Save Settings"):
            save_config(config)
            st.sidebar.success("Settings saved successfully!")
        

    # Generate app button
    if st.button("Build Flutter App"):
        try:
            validated_app_name = validate_app_name(app_name) 
        except ValueError as e:
            st.error(str(e)) 
            return # Stop execution if validation fails
        if not config["openai_api_key"]:
            st.error("Please enter your OpenAI API key in the settings.")
        elif not config["flutter_sdk_path"]:
            st.error("Please enter the path to your Flutter SDK in the settings.")
        elif not instructions:
            st.error("Please enter app instructions.")
        else:
             with st.spinner("Generating Flutter app..."):
                try:
                    # --- Code Generation (with Progress Bar) ---
                    cache_key = get_cache_key(instructions, mode, state_management, target_platform, database_type)
                    cached_result = get_cached_result(cache_key)
                    
                    if cached_result:
                        st.info("Using cached result")
                        main_dart_content, screens_widgets_content, networking_content, database_content, auth_content = cached_result
                    else:
                        # Use tqdm for progress bars during code generation
                        with tqdm(total=5, desc="Generating Code", bar_format="{l_bar}{bar} [Time remaining: {remaining}]") as pbar:
                            main_dart_content = generate_flutter_app_code(instructions, mode, state_management, config)
                            pbar.update(1)
                            screens_widgets_content = generate_screens_and_widgets(instructions, app_name)
                            pbar.update(1)
                            networking_content = generate_networking_code(instructions, app_name)
                            pbar.update(1)
                            database_content = generate_database_code(instructions, app_name, database_type) if database_type != 'None' else ''
                            pbar.update(1)
                            auth_content = generate_authentication_code(instructions, app_name)
                            pbar.update(1)
                            
                            save_to_cache(cache_key, (main_dart_content, screens_widgets_content, networking_content, database_content, auth_content))
                    # --- End Code Generation ---

                    # Review and debug code using Swarm agents
                    reviewed_main_dart = review_and_debug_code(swarm, 
                                                               code_review_agent,  # CodeReviewAgent
                                                               debugging_agent,     # DebuggingAgent
                                                               main_dart_content, 
                                                               "main.dart")
                    reviewed_screens_widgets = review_and_debug_code(swarm, 
                                                                     code_review_agent, 
                                                                     debugging_agent, 
                                                                     screens_widgets_content, 
                                                                     "screens_widgets.dart")
                    reviewed_networking = review_and_debug_code(swarm, 
                                                                 code_review_agent, 
                                                                 debugging_agent, 
                                                                 networking_content, 
                                                                 "networking.dart")
                    reviewed_database = review_and_debug_code(swarm, 
                                                               code_review_agent, 
                                                               debugging_agent, 
                                                               database_content, 
                                                               "database.dart")
                    reviewed_auth = review_and_debug_code(swarm, 
                                                          code_review_agent, 
                                                          debugging_agent, 
                                                          auth_content, 
                                                          "authentication.dart")
                    
                    # Generate project structure
                    project_path = generate_flutter_project_structure(app_name, ",".join(target_platform), config["flutter_sdk_path"])

                    # Write reviewed code to files
                    for file_name, content in [
                        ("main.dart", reviewed_main_dart),
                        ("screens_widgets.dart", reviewed_screens_widgets),
                        ("networking.dart", reviewed_networking),
                        ("database.dart", reviewed_database),
                        ("authentication.dart", reviewed_auth)
                    ]:
                        with open(os.path.join(project_path, "lib", file_name), "w") as f:
                            f.write(content)

                    try:
                        initialize_git_repo(project_path, config["git_repo_url"])
                    except Exception as git_error:
                        # More user-friendly error handling for Git operations
                        st.warning(f"Git initialization or push failed. "
                                   f"You can manually initialize the repository later.")
                        logging.warning(f"Git initialization or push failed: {str(git_error)}")

                    st.subheader("Generated main.dart:")
                    st.code(reviewed_main_dart, language="dart")

                    zip_file = create_zip_file(project_path)
                    st.download_button(
                        "Download Flutter App",
                        zip_file,
                        f"{app_name}.zip",
                        "application/zip",
                        key="download_app"
                    )

                    st.success("Flutter app generated successfully!")

                    shutil.rmtree(os.path.dirname(project_path))

                except (TimeoutError, RuntimeError) as e: 
                    st.error(str(e))  # Display timeout or runtime error
                    logging.exception("Error in app generation process") 
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    logging.exception("Error in app generation process")

                    # --- Error Recovery Options ---

                    # 1. Provide more specific error messages to the user
                    if hasattr(e, 'stderr'):
                        st.error(f"Error details: {e.stderr.decode()}")
                    
                    # 2. Offer suggestions based on the error type
                    if isinstance(e, subprocess.CalledProcessError):
                        st.warning("Check your Flutter SDK path and ensure Flutter is installed correctly.")
                    elif isinstance(e, openai.error.OpenAIError):
                        st.warning("OpenAI API error. Check your API key and try again later.")

                    # 3. Allow the user to retry the operation
                    if st.button("Retry"):
                        # Retry the app generation process
                        # You may need to reset some variables or clear the cache
                        pass  

                    # 4. Guide the user to seek help
                    st.info("For further assistance, please refer to the documentation or contact support.")

        # User feedback
        st.subheader("Feedback")
        user_rating = st.slider("Rate your experience", 1, 5, 3)
        user_feedback = st.text_area("Provide feedback (optional)")
        if st.button("Submit Feedback"):
            # Here you would typically save the feedback to a database or file
            st.success("Thank you for your feedback!")

    with right_column:
        # Add a visualizer at the top
        st.header("App Generation Progress")

        # Example data for the visualizer
        progress_data = {
            'Step': ['Step 01: App Basics', 'Step 02: Project Setup', 'Step 03: App Instructions', 'Step 04: Code Generation', 'Step 05: Review and Debug', 'Step 06: Project Structure', 'Step 07: Write Code', 'Step 08: Initialize Git', 'Step 09: Create Zip', 'Step 10: Complete'],
            'Progress': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        }

        progress_df = pd.DataFrame(progress_data)

        # Use a bar chart to visualize the progress
        st.bar_chart(progress_df.set_index('Step'))
        st.subheader("Generated Code")
            
        # Create tabs for different code files
        tabs = st.tabs(["main.dart", "screens_widgets.dart", "networking.dart", "database.dart", "authentication.dart", "Help and Documentation"])
            
        # Display code in respective tabs
        with tabs[0]:
                if 'main_dart_content' in locals():
                    st.code(main_dart_content, language="dart")
                else:
                    st.info("Generate the app to see the main.dart code here.")
        
        with tabs[1]:
                if 'screens_widgets_content' in locals():
                    st.code(screens_widgets_content, language="dart")
                else:
                    st.info("Generate the app to see the screens and widgets code here.")
        
        with tabs[2]:
                if 'networking_content' in locals():
                    st.code(networking_content, language="dart")
                else:
                    st.info("Generate the app to see the networking code here.")
        
        with tabs[3]:
                if 'database_content' in locals():
                    st.code(database_content, language="dart")
                else:
                    st.info("Generate the app to see the database code here.")
        
        with tabs[4]:
                if 'auth_content' in locals():
                    st.code(auth_content, language="dart")
                else:
                    st.info("Generate the app to see the authentication code here.")
    
        with tabs[5]:
                st.markdown("""
                ## Help and Documentation
    
                ### Overview
                This application helps you generate a Flutter app based on your instructions. You can specify the mode, state management, target platforms, and database type.
    
                ### Steps to Generate an App
                1. **Select Mode**: Choose between UI Designer, Full-Stack Developer, or Mobile App Specialist.
                   - **UI Designer**: Focuses on creating a beautiful and intuitive user interface.
                   - **Full-Stack Developer**: Integrates both frontend and backend functionalities.
                   - **Mobile App Specialist**: Optimizes the app for mobile devices with specific features.
                2. **Select State Management**: Choose between Provider, BLoC, or Riverpod.
                   - **Provider**: Simple and easy to use, suitable for small to medium-sized apps.
                   - **BLoC**: Business Logic Component, ideal for large-scale apps with complex state management.
                   - **Riverpod**: A more flexible and powerful alternative to Provider, with better performance.
                3. **Select Target Platforms**: Choose the platforms you want to target (e.g., Android, iOS, Web).
                   - **Android**: For Android devices.
                   - **iOS**: For Apple devices.
                   - **Web**: For web applications.
                   - **Windows**: For Windows desktop applications.
                   - **macOS**: For macOS desktop applications.
                   - **Linux**: For Linux desktop applications.
                4. **Select Database Type**: Choose between SQLite, Firestore, or Hive.
                   - **SQLite**: A lightweight, file-based database, suitable for local storage.
                   - **Firestore**: A cloud-based NoSQL database, ideal for real-time data synchronization.
                   - **Hive**: A lightweight and fast key-value database, suitable for local storage with minimal overhead.
                5. **Enter Instructions**: Provide detailed instructions for the app you want to generate.
                6. **Enter App Name**: Provide a name for your app.
                7. **Build Flutter App**: Click the button to generate the app.
    
                ### Tips for Giving Instructions
                - **Be Specific**: Clearly describe the features and functionalities you want in your app.
                - **Include Examples**: Provide examples or references to similar apps to help convey your vision.
                - **Detail UI/UX Requirements**: Specify any design preferences, color schemes, or layout requirements.
                - **Mention Integrations**: If your app needs to integrate with third-party services or APIs, mention them.
                - **State Management**: Indicate how you want the state to be managed (e.g., using Provider, BLoC, or Riverpod).
                - **Platform-Specific Features**: Highlight any features that should be unique to certain platforms (e.g., iOS-specific gestures).
                - **Performance Considerations**: Mention any performance requirements or constraints.
    
                ### Settings
                - **OpenAI API Key**: Enter your OpenAI API key.
                - **Git Repository URL**: Enter the URL of your Git repository.
                - **Output Folder**: Specify the folder where the generated app will be saved.
                - **Flutter SDK Path**: Specify the path to your Flutter SDK.
    
                ### Feedback
                After generating the app, you can provide feedback to help improve the tool.
    
                ### Troubleshooting
                - Ensure you have entered all required information.
                - Check the logs for any errors during the generation process.
                - If you encounter issues, try clearing the cache and regenerating the app.
    
                For more detailed documentation, visit the [official documentation](https://flutter.dev/docs).
                """)

if __name__ == "__main__":
    main()
