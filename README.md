# CS-499 Capstone Final Project

### Project Members: Logan Miles, Daniel Eleam, Hunter Skelton, Ryan Cruce, Taylor Borden, Valeria Vergara

## Project Description:
The goal of this project was to develop a web application to streamline the pet adoption process and make it more user-friendly. The project required both front-end and back-end development. We utilized HTML and CSS to build a user  interface, Flask to handle routing and server-side functionality, and a self-hosted MySQL connection to manage pet data, including details like name, breed, age, and vaccination status. The application was hosted on Google Cloud Run, with Cloud Build automating deployments through GitHub Actions. Additionally, Cloud Storage was used for storing images and other assets.

## Features

### User Registration and Authentication  
- Secure account creation and login  
- Authentication with encrypted credentials stored in SQL Server  

### User Accounts and Profiles  
- Profile management for adopters  
- Shelter organization profiles with pet listings

### User Interaction
- User search
- User posts including text, images, and video
- Likes and comments
- User following system
- Notifications for follow/adoption requests

### Pet Listing and Search  
- Display pets with details (breed, age, vaccination status, etc.)  
- Search filters based on pet characteristics  

### Saved Pets  
- Bookmark pets for later viewing  
- Dedicated "Saved Pets" section  

### Adoption Process  
- Submit adoption applications  
- Schedule pet pickups  
- Process payments for applicable adoptions  
- Update pet availability post-adoption  

### Shelter Management
- Shelter pages display pets up for adoption at shelters
- Shelter page requests can only be approved by site admin
- Shelter staff can:
  - Send request to add other staff members
  - View/add/remove pets associated with shelter that were posted by staff members
  - View pet adoption history from the shelter
  - View/approve/deny adoption requests for pets associated with shelter


## Repo structure:

├── **app.py**  - *Main Flask application file, contains routes and app configuration.*  
├── **models.py**  - *Database models and helper functions for interacting with the database.*  
├── **.gitignore**  - *Specifies files and directories to be ignored by Git.*  
├── **Dockerfile**  - *Instructions for building the Docker image for the application.*  
├── **docker-compose.yaml**  - *Configuration for running the application with Docker Compose.*  
├── **requirements.txt**  - *List of Python dependencies required for the project.*  
├── **package-lock.json**  - *Auto-generated file for locking Node.js dependencies.*  
├── **package.json**  - *Configuration file for managing Node.js dependencies.*  
├── **templates/**  - *Directory containing HTML templates for the application.*  
│   ├── **404.html**  - *Custom 404 error page.*   
│   ├── **500.html**  - *Custom 500 error page.*  
│   ├── **about.html**  - *About page.*  
│   ├── **add_shelter.html**  - *Template for creating shelters.*  
│   ├── **adopt_pet_application.html**  - *Template for filling out pet adoption application.*  
│   ├── **create_post.html**  - *Template for creating a new post.*  
│   ├── **edit_profile.html**  - *Template for editing user profiles.*  
│   ├── **edit_post_and_pet.html**  - *Template for editing pet entries and posts on homepage.*  
│   ├── **faq.html**  - *FAQ page.*  
│   ├── **index.html**  - *Homepage template displaying posts.*  
│   ├── **login.html**  - *Template for user login.*  
│   ├── **login.html**  - *Template for managing shelter.*  
│   ├── **navbar.html**  - *Shared navigation bar template.*  
│   ├── **post_page.html**  - *Template for viewing a single post.*  
│   ├── **profile.html**  - *Template for viewing user profiles.*  
│   ├── **register.html**  - *Template for user registration.*  
│   ├── **saved_pets.html**  - *Template for displaying saved pets.*  
│   ├── **search.html**  - *Template for searching users.*  
│   ├── **shelter_details.html**  - *Template for displaying shelter details for non-staff members.*  
│   ├── **shelter_list.html**  - *Template for displaying all shelters.*  
│   ├── **shelter_requests.html**  - *Template for displaying all shelter requests for admins.*  
│   ├── **search_pets.html**  - *Template for searching pets.*  
│   ├── **thankyou.html**  - *Template for the thank-you page after registration.*  
│   ├── **view_pet.html**  - *Template for viewing a single pet's details.*  
│   ├── **view_adoption_aplications.html**  - *Template for viewing adoption applications.*  
├── **static/**  - *Directory containing static assets like CSS and images.*  
│   ├── **style.css**  - *Main stylesheet for the application.*  
│   ├── **assets/**  - *Directory for additional static assets.*  
│   │   ├── **like-unliked.png**  - *Icon for the like button.*  
│   │   ├── **like-liked.png**  - *Icon for the like button after liking a post.*  
│   │   ├── **logo.png**  - *Main logo for the application.*  
│   │   ├── **logo_small.png**  - *Smaller version of the application logo.*  
│   ├── **cursor/**  - *Directory for additional cursor assets.*  
│   │   ├── **cursor-unselect.png**  - *Icon for the paw cursor.*  
│   │   ├── **cursor-select.png**  - *Icon for the paw cursor when hovering.*  
│   ├── **profile_pics/**  - *Directory for storing user profile pictures.*  
│   │   ├── **default.png**  - *Default profile picture for users.*  

## Instructions to deploy the Flask app locally:

1. Create a Python virtual environment or download and install [Conda](https://www.anaconda.com/download) and then select it as your interpreter within your IDE.
2. Clone the Git repository. Make sure that the folder you clone the repo into is accessible by the Conda interpreter or the virtual environment.
3. Run the following command to download and install the required Python libraries: `pip install -r requirements.txt`
4. Change `LOCAL_TESTING` variable to `True` at line 26 of app.py.
5. Run the app.py file to start the flask app: `python app.py`
6. The Flask app should begin running on your machine and you can access it at `https://localhost:8080` or the ip address provided in the terminal when the app is started.

### References
- https://www.youtube.com/watch?v=-FWuNnCe73g
- https://medium.com/codex/continuously-deploying-a-flask-app-from-a-github-repository-to-google-cloud-run-6f26226539b0
- https://www.geeksforgeeks.org/setting-up-google-cloud-sql-with-flask/
- https://stackoverflow.com/questions/8160494/how-to-make-a-whole-div-clickable-in-html-and-css-without-javascript
- https://stackoverflow.com/questions/34027368/css-text-input-field-not-aligning-top-left
- https://stackoverflow.com/questions/14993318/catching-a-500-server-error-in-flask
- https://stackoverflow.com/questions/41865214/how-to-serve-an-image-from-google-cloud-storage-using-python-flask
- https://help.retentionscience.com/hc/en-us/articles/115003025814-How-To-Build-HTML-for-Conditional-Statements
- https://stackoverflow.com/questions/43041253/how-to-set-flask-server-timezone-to-gmt
- https://www.javatpoint.com/javascript-domcontentloaded-event
