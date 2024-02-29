from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import json
from threading import Thread, Event

app = Flask(__name__)
app.config['SECRET_KEY'] = 'geheim!'
app.config['UPLOAD_FOLDER'] = 'uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

events = {
    "1": {
        "time": "2",
        "event": "location"
    },
    "2": {
        "time": "1",
        "event": "picture"
    }
}

socketio = SocketIO(app)

last_image_filename = None

game_start_time = None

stop_event = Event()

triggered_events = set()

is_photo_uploaded = True
is_location_uploaded = True

latitude = 0
longitude = 0

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@socketio.on('request_start_time')
def handle_request_start_time():
    if game_start_time:
        emit('game_start_time', {'start_time': game_start_time.strftime('%Y-%m-%d %H:%M:%S')})

@app.route('/force_picture')
def force_picture():
    global is_photo_uploaded
    is_photo_uploaded = False
    socketio.emit('trigger_event', {'event': 'picture'})
    return redirect(url_for('beheerder'))

@app.route('/force_location')
def force_location():
    global is_location_uploaded
    is_location_uploaded = False
    socketio.emit('trigger_event', {'event': 'location'})
    return redirect(url_for('beheerder'))

@app.route('/beheerder')
def beheerder():
    return render_template('beheerder.html')

@app.route('/jagers')
def jagers():
    return render_template('jagers.html')

@app.route('/verstoppers')
def verstoppers():
    return render_template('verstoppers.html')

def check_events():
    global is_photo_uploaded
    global is_location_uploaded
    """Checkt de gedefinieerde events en stuurt berichten naar de client."""
    while not stop_event.is_set() and game_start_time:
        current_time = datetime.now()
        elapsed_time = (current_time - game_start_time).total_seconds() / 60
        for event_id, event_info in events.items():
            event_time = float(event_info['time'])
            # Controleer of de huidige tijd binnen de minuut van het event valt
            # en of het event nog niet getriggerd is
            if event_time <= elapsed_time < event_time + 1 and event_id not in triggered_events:
                socketio.emit('trigger_event', {'event': event_info['event']})
                if event_info['event'] == 'picture':
                    is_photo_uploaded = False
                if event_info['event'] == 'location':
                    is_location_uploaded = False
                triggered_events.add(event_id)  # Voeg toe aan de set van getriggerde events

@app.route('/start_game', methods=['POST'])
def start_game():
    global game_start_time, triggered_events
    game_start_time = datetime.now()
    triggered_events.clear()  # Reset de set van getriggerde events
    stop_event.clear()
    thread = Thread(target=check_events)
    thread.start()

    socketio.emit('game_started', {'start_time': game_start_time.strftime('%Y-%m-%d %H:%M:%S')})
    return redirect(url_for('beheerder'))

@app.route('/stop_game', methods=['POST'])
def stop_game():
    global is_location_uploaded
    global is_photo_uploaded
    global latitude
    global longitude
    global game_start_time
    global last_image_filename
    last_image_filename = ""
    latitude = 0
    longitude = 0
    game_start_time = None
    is_photo_uploaded = True
    is_location_uploaded = True
    # Zet een vlag om de achtergrondtaak te stoppen
    stop_event.set()
    socketio.emit('game_stopped')
    return redirect(url_for('beheerder'))

@app.route('/upload_image', methods=['POST'])
def upload_image():
    global is_photo_uploaded
    global last_image_filename  # Vergeet niet deze global declaration te gebruiken
    if 'file' not in request.files:
        return 'Geen bestand deel van het verzoek.', 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return 'Ongeldig bestandsformaat.', 400
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    last_image_filename = filename  # Update de variabele met de nieuwe filename
    socketio.emit('image_uploaded', {'filename': filename})
    socketio.emit('foto_uploaded')
    is_photo_uploaded = True
    return redirect(url_for('verstoppers'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/get_last_image')
def get_last_image():
    if last_image_filename:
        return {'filename': last_image_filename}
    else:
        return {'filename': ''}  # Of stuur een standaardafbeeldingsnaam
    
@app.route('/is_photo_uploaded')
def isphotouploaded():
    if is_photo_uploaded == True:
        return {'is_photo_uploaded': 'yes'}
    if is_photo_uploaded == False:
        socketio.emit('trigger_event', {'event': 'picture'})
        return {'is_photo_uploaded': 'no'}
    
@app.route('/is_location_uploaded')
def islocationuploaded():
    if is_location_uploaded == True:
        return {'is_location_uploaded': 'yes'}
    if is_location_uploaded == False:
        socketio.emit('trigger_event', {'event': 'location'})
        return {'is_location_uploaded': 'no'}
    
    
@app.route('/send_location', methods=['POST'])
def receive_location():
    global is_location_uploaded
    global latitude
    global longitude
    if is_location_uploaded == True:
        return {'is_location_uploaded': 'yes'}
    if is_location_uploaded == False:
        data = request.json
        latitude = data['latitude']
        longitude = data['longitude']

        is_location_uploaded = True
        
        # Verwerk de locatie, zoals het opslaan in een database
        # Voor nu printen we het gewoon
        print(f"Ontvangen locatie: Latitude: {latitude}, Longitude: {longitude}")

        socketio.emit('location_update')
        
        # Stuur een bevestiging terug naar de client
        return {"status": "success"}
    
@app.route('/get_location')
def get_location():
    return {'lat': latitude, 'long': longitude}


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=25582)
