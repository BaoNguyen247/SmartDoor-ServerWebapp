let registrationProgress = 0;
let progressInterval;

function initializeRegistrationCamera() {
    const video = document.getElementById('registration-video');
    
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            video.srcObject = stream;
        })
        .catch(err => {
            console.error('Lỗi truy cập camera đăng ký:', err);
        });
}

document.getElementById('registration-form').addEventListener('submit', function(e) {
    e.preventDefault();
    console.log('Registration form submit handler called');
    
    const fullname = document.getElementById('fullname').value;
    const gender = document.getElementById('gender').value;
    const phone = document.getElementById('phone').value;
    const department = document.getElementById('department').value;
    
    if (!fullname || !gender || !phone || !department) {
        alert('Vui lòng điền đầy đủ thông tin!');
        return;
    }
    
    // Start backend add-face job and update UI accordingly
    console.log('Starting registration job for', fullname);
    startRegistrationJob({
        name: fullname,
        camera: 0,
        images: 100,
        interval: 10,
        nodisplay: false,
    }, e.target);
});


/**
 * Start the add-face job on the backend and poll status.
 * payload: { name, camera, images, interval, nodisplay }
 * formElement: the <form> element that triggered the submit (used to disable the submit button)
 */
function startRegistrationJob(payload, formElement) {
    const submitButton = formElement.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    const processedFeed = document.getElementById('processed-video-feed-registration') || document.getElementById('processed-video-feed');
    const streamUrl = 'http://localhost:8000/video_feed';

    // Start processed MJPEG stream for visual feedback
    if (processedFeed) {
        processedFeed.src = streamUrl;
    }

    registrationProgress = 0;
    const progressCircle = document.getElementById('progress-circle');
    const progressText = document.getElementById('progress-text');

    // Start a gentle animated progress while the job runs
    if (progressCircle) progressCircle.style.strokeDashoffset = 314;
    if (progressText) progressText.textContent = '0%';

    // Soft progress increment (will be capped by job completion)
    progressInterval = setInterval(() => {
        registrationProgress = Math.min(98, registrationProgress + 1); // don't reach 100 until backend says done
        const offset = 314 - (314 * registrationProgress / 100);
        if (progressCircle) progressCircle.style.strokeDashoffset = offset;
        if (progressText) progressText.textContent = registrationProgress + '%';
    }, 500);

    // Call backend to start job
    fetch('http://localhost:8000/api/add_face', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => {
        if (!res.ok) throw new Error('Failed to start registration job');
        return res.json();
    })
    .then(data => {
        const jobId = data.job_id;
        console.log('Registration job started:', jobId);

        // Poll status every 2 seconds
        const pollInterval = setInterval(() => {
            fetch(`http://localhost:8000/api/add_face/status/${jobId}`)
                .then(r => r.json())
                .then(status => {
                    if (status.status === 'running') {
                        // keep soft progress
                        return;
                    }

                    // Job finished (done or error)
                    clearInterval(pollInterval);
                    clearInterval(progressInterval);

                    if (status.status === 'done') {
                        registrationProgress = 100;
                        const offset = 314 - (314 * registrationProgress / 100);
                        if (progressCircle) progressCircle.style.strokeDashoffset = offset;
                        if (progressText) progressText.textContent = registrationProgress + '%';

                        setTimeout(() => {
                            alert('Đăng ký khuôn mặt thành công!');
                            resetRegistrationForm();
                        }, 300);
                    } else {
                        const err = status.error || 'Unknown error';
                        alert('Đăng ký thất bại: ' + err);
                    }

                    // Stop processed stream
                    if (processedFeed) {
                        processedFeed.src = '';
                    }

                    if (submitButton) submitButton.disabled = false;
                })
                .catch(err => {
                    console.error('Status poll error:', err);
                    // Keep polling — or you could stop after repeated failures
                });
        }, 2000);
    })
    .catch(err => {
        clearInterval(progressInterval);
        if (processedFeed) processedFeed.src = '';
        if (submitButton) submitButton.disabled = false;
        alert('Không thể bắt đầu quá trình đăng ký: ' + err.message);
        console.error(err);
    });
}


/**
 * Handles switching between different application sections (tabs).
 * @param {string} sectionId - The ID of the section to show (e.g., 'face-registration').
 */
function showSection(sectionId) {
    // 1. Hide ALL sections and remove the active class from ALL sidebar items
    const sections = ['face-recognition', 'face-registration', 'door-control', 'history'];
    
    sections.forEach(id => {
        const sectionElement = document.getElementById(id);
        if (sectionElement) {
            sectionElement.classList.add('hidden');
        }
    });

    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.remove('active');
        item.classList.remove('bg-blue-50'); // Tailwind class for background
        item.querySelector('svg').classList.remove('text-blue-700'); // Tailwind class for icon color
        item.querySelector('span').classList.remove('font-bold'); // Tailwind class for text style
    });

    // 2. Show the requested section and set the sidebar item to active
    const requestedSection = document.getElementById(sectionId);
    const sidebarItem = document.querySelector(`.sidebar-item[onclick*="${sectionId}"]`);
    
    if (requestedSection) {
        requestedSection.classList.remove('hidden');
    }
    
    if (sidebarItem) {
        sidebarItem.classList.add('active');
        sidebarItem.classList.add('bg-blue-50');
        sidebarItem.querySelector('svg').classList.add('text-blue-700');
        sidebarItem.querySelector('span').classList.add('font-bold');
    }

    // 3. CAMERA CONTROL LOGIC (The fix for your camera issue!):
    if (sectionId === 'face-registration') {
        // Start the camera ONLY when the registration tab is active
        initializeRegistrationCamera(); 
        console.log("Registration camera initialized.");
    } else {
        // Stop the camera stream when navigating away from the registration tab
        stopRegistrationCamera(); 
    }
}

// --- INITIALIZATION ---
// Note: Do not force showing any section here. `app.js` is responsible for
// initial section selection. Keeping this file focused on registration logic
// prevents accidentally switching tabs while registration is in progress.


function startRegistrationProgress() {
    registrationProgress = 0;
    const progressCircle = document.getElementById('progress-circle');
    const progressText = document.getElementById('progress-text');
    // Prefer the registration-specific processed feed (small rectangle)
    const processedFeed = document.getElementById('processed-video-feed-registration') || document.getElementById('processed-video-feed');
    const streamUrl = 'http://localhost:8000/video_feed';

    // Start the processed MJPEG stream (same as faceRecognition.js)
    if (processedFeed) {
        processedFeed.src = streamUrl;
        console.log('Processed video stream started from (registration):', streamUrl);
    }
    
    progressInterval = setInterval(() => {
        registrationProgress += 2;
        
        const offset = 314 - (314 * registrationProgress / 100);
        progressCircle.style.strokeDashoffset = offset;
        progressText.textContent = registrationProgress + '%';
        
        if (registrationProgress >= 100) {
            clearInterval(progressInterval);
            setTimeout(() => {
                alert('Đăng ký khuôn mặt thành công!');
                resetRegistrationForm();
                // Stop the processed stream after a short delay so the user can see the final frame
                if (processedFeed) {
                    // Clearing the src will stop the MJPEG stream in most browsers
                    processedFeed.src = '';
                    console.log('Processed video stream stopped (registration complete).');
                }
            }, 500);
        }
    }, 100);
}

// Add this function to your faceRegistration.js or app.js
function stopRegistrationCamera() {
    const video = document.getElementById('registration-video');
    const stream = video.srcObject;
    if (stream) {
        // Stop all tracks (video, audio) in the stream
        stream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }
}

function resetRegistrationForm() {
    document.getElementById('registration-form').reset();
    registrationProgress = 0;
    document.getElementById('progress-circle').style.strokeDashoffset = 314;
    document.getElementById('progress-text').textContent = '0%';
}