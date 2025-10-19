const streamUrl = 'http://localhost:8000/video_feed';

function startProcessedStream() {
    const streamElement = document.getElementById('processed-video-feed');
    if (!streamElement) {
        console.error('[faceRecognition] Element #processed-video-feed not found');
        return;
    }
    
    streamElement.src = streamUrl;
    console.log('[faceRecognition] Processed video stream started from:', streamUrl);
}

// Initialize stream when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('[faceRecognition] Page loaded, initializing stream...');
    startProcessedStream();
});

// Also restart stream when switching to face-recognition tab
function onFaceRecognitionTabActive() {
    startProcessedStream();
}