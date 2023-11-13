from flask import Flask, redirect, request, session, render_template
import config
import base64
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Check if the access token is expired or needs refreshing
def is_token_expired(expiration_time):
    # Add a threshold (e.g., 5 minutes) to ensure the token is refreshed before expiration
    print(expiration_time)
    expiration_threshold = timedelta(minutes=5)
    return expiration_time - datetime.now(pytz.utc) < expiration_threshold

def fetch_spotify_tracks(endpoint_url, access_token):
    tracks = []
    while endpoint_url:
        response = requests.get(endpoint_url, headers={'Authorization': f'Bearer {access_token}'})
        if response.status_code == 200:
            data = response.json()
            tracks.extend(data.get('items', []))
            endpoint_url = data.get('next')  # URL for the next page of results
        else:
            print(f'Error: {response.status_code}')
            break
    return tracks

app = Flask(__name__)
app.secret_key = config.APP_SECRET

# Define the Spotify API credentials
CLIENT_ID = config.SPOTIFY_CLIENT_ID
CLIENT_SECRET = config.SPOTIFY_CLIENT_SECRET
REDIRECT_URI = config.REDIRECT_URI

@app.route('/')
def homepage():
    authentication_status = session.get('authenticated', False)
    return render_template('index.html', authenticated=authentication_status)

@app.route('/authenticate')
def authenticate():
    # Redirect the user to the Spotify login page
    # Scopes: https://developer.spotify.com/documentation/web-api/concepts/scopes#user-library-read, user-library-read is required for getting user's saved track, user-top-read is for getting user's top tracks/artists
    spotify_auth_url = f"https://accounts.spotify.com/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=user-library-read,user-top-read"
    return redirect(spotify_auth_url)

@app.route('/callback/')
def callback():
    # Get the authorization code from the query parameters
    auth_code = request.args['code']

    # Exchange the authorization code for an access token
    token_url = "https://accounts.spotify.com/api/token"
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = {
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    response = requests.post(token_url, data=data, headers={'Authorization': f'Basic {auth_header}'})

    # Store the access token in the session (in a real application, use a secure storage method)
    access_token = response.json().get('access_token')
    expires_in = response.json().get('expires_in')
    current_time = datetime.now(pytz.utc)
    token_expiration_time = current_time + timedelta(seconds=expires_in)
    
    session['access_token'] = access_token
    session['token_expiration'] = token_expiration_time

    # Redirect to a page where you can make API requests
    session['authenticated'] = True
    return redirect('/')

@app.route('/retrieve/saved-tracks')
def retrieve_saved_tracks():
    access_token = session.get('access_token')
    expiration_time = session.get('token_expiration')
    if access_token and not is_token_expired(expiration_time):
        saved_tracks = []
        try:
            # Spotify API endpoint for getting the user's saved tracks
            endpoint_url = 'https://api.spotify.com/v1/me/tracks'

            # Fetch tracks from the Spotify API
            spotify_tracks = fetch_spotify_tracks(endpoint_url, access_token)

            # Process the tracks (print names as an example)
            for track in spotify_tracks:
                track_added_at = track['added_at']
                if len(track['track']['album']['images']) != 0:
                    track_image = track['track']['album']['images'][0]['url']
                else:
                    track_image = 'Not Available'
                track_album_name = track['track']['album']['name']
                track_url = track['track']['external_urls']['spotify']
                track_artist = track['track']['artists'][0]['name']
                track_name = track['track']['name']
                track_popularity = track['track']['popularity']
                track_preview_url = track['track']['preview_url']
                saved_tracks.append([track_name, track_album_name, track_artist, track_popularity, track_added_at, track_url, track_image, track_preview_url])
        except requests.exceptions.HTTPError as err:
            print(err.response.text)  # Print the full API error response for debugging purposes
            return 'Error occurred while fetching saved tracks. Please try again later.', 500
        finally:
            pd.DataFrame(saved_tracks, columns = ['track_name', 'track_album_name', 'track_artist', 'track_popularity', 'track_added_at', 'external_url', 'track_image', 'track_preview_url']).to_csv('saved_tracks.csv')
            session['saved_tracks'] = saved_tracks[0:10]
        return redirect('/')
    else:
        return redirect('/authenticate')
    
@app.route('/retrieve/top-artists')
def retrieve_top_artists():
    access_token = session.get('access_token')
    expiration_time = session.get('token_expiration')
    if access_token and not is_token_expired(expiration_time):
        top_artists = []
        try:
            top_artists_response = requests.get('https://api.spotify.com/v1/me/top/artists?limit=50', headers={'Authorization': f'Bearer {access_token}'})
            top_artists_response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes
            top_artists_data = top_artists_response.json()
            
            # Extract relevant information
            for artists in top_artists_data['items']:
                artist_name = artists['name']
                artist_popularity = artists['popularity']
                artist_external_url = artists['external_urls']['spotify']
                artist_genres = artists['genres']
                if len(artists['images']) >= 1:
                    artist_image = artists['images'][0]['url']
                else:
                    artist_image = ''
                top_artists.append([artist_name, artist_popularity, artist_external_url, artist_genres, artist_image])
            
        except requests.exceptions.HTTPError as err:
            print(err.response.text)  # Print the full API error response for debugging purposes
            return 'Error occurred while fetching top artists. Please try again later.', 500
        
        finally:
            pd.DataFrame(top_artists, columns=['artist_name', 'artist_popularity', 'artist_external_url', 'artist_genres', 'artist_image']).to_csv('top_artists_2023.csv')
            session['top_artists'] = top_artists[0:10]
        return redirect('/')
    else:
        redirect('/authenticate')

@app.route('/retrieve/top-tracks')
def retrieve_top_tracks():
    access_token = session.get('access_token')
    expiration_time = session.get('token_expiration')
    if access_token and not is_token_expired(expiration_time):
        top_tracks = []
        try:
            # Get user's top 50 tracks from Spotify API
            top_tracks_response = requests.get('https://api.spotify.com/v1/me/top/tracks?limit=50', headers={'Authorization': f'Bearer {access_token}'})
            top_tracks_response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes
            top_tracks_data = top_tracks_response.json()
            
            # Extract relevant information
            for track in top_tracks_data['items']:    
                # Album Link
                album_link = track['album']['external_urls']['spotify']
                album_image = track['album']['images'][0]['url']
                album_name = track['album']['name']
                track_name = track['name']
                track_url = track['external_urls']['spotify']
                album_release_date = track['album']['release_date']
                artist_name = track['album']['artists'][0]['name']
                popularity = track['popularity']
                preview_url = track['preview_url']
                
                top_tracks.append([artist_name,track_name,track_url,popularity,album_name,album_release_date,album_image,album_link,preview_url])
                
        except requests.exceptions.HTTPError as err:
            print(err.response.text)  # Print the full API error response for debugging purposes
            return 'Error occurred while fetching top tracks. Please try again later.', 500
        
        finally:
            pd.DataFrame(top_tracks, columns=['artist_name','track_name','track_url','popularity','album_name','album_release_date','album_image','album_link','preview_url']).to_csv('top_tracks_2023.csv')
            session['top_tracks'] = top_tracks[0:10]
        return redirect('/')
    else:
        return redirect('/authenticate')

@app.route('/clearScreen')
def clearScreen():
    if 'saved_tracks' in session:
        del session['saved_tracks']
    if 'top_tracks' in session:
        del session['top_tracks']
    if 'top_artists' in session:
        del session['top_artists'] 
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)