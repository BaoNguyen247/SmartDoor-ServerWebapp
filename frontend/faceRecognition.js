function startProcessedStream() {
    const streamElement = document.getElementById('processed-video-feed');
    const streamUrl = 'http://localhost:8000/video_feed'; 

    // Set the source of the <img> element to start the MJPEG stream
    streamElement.src = streamUrl;

    console.log('Processed video stream started from:', streamUrl);
}

// Example of calling the function when the page loads
document.addEventListener('DOMContentLoaded', startProcessedStream);


// ⚠️ KEEP THIS DUMMY FUNCTION FOR NOW, but note it must be replaced
// with an API poll (fetch) for real results.
function startFaceRecognition() {
    // Note: The global 'currentSection' variable is assumed to be defined elsewhere.
    setInterval(() => {
        if (currentSection === 'face-recognition') {
            const accuracy = Math.floor(Math.random() * 100);
            document.getElementById('accuracy').textContent = accuracy + '%';
            
            if (accuracy > 80) {
                document.getElementById('person-id').textContent = 'NV' + String(Math.floor(Math.random() * 999) + 1).padStart(3, '0');
            } else {
                document.getElementById('person-id').textContent = 'Unknown';
            }
        }
    }, 2000);
}