document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('videoFileInput');
    const selectedFileInfo = document.getElementById('selectedFileInfo');
    const selectedFileName = document.getElementById('selectedFileName');
    const selectedFileSize = document.getElementById('selectedFileSize');
    const btnStart = document.getElementById('btnStartAnalysis');
    const uploadForm = document.getElementById('uploadForm');
    const processingSection = document.getElementById('processingSection');
    const progressBarFill = document.getElementById('progressBarFill');
    const statusMessage = document.getElementById('statusMessage');
    const statusPercent = document.getElementById('statusPercent');
    const resultsSection = document.getElementById('resultsSection');

    // Drive Modal Elements
    const btnOpenDrive = document.getElementById('btnOpenDriveModal');
    const btnCloseDrive = document.getElementById('btnCloseDriveModal');
    const btnCancelDrive = document.getElementById('btnCancelDrive');
    const driveModal = document.getElementById('driveModal');
    const driveSettingsForm = document.getElementById('driveSettingsForm');

    let currentFile = null;
    let pollInterval = null;
    let biomechanicsChart = null;

    // Drag and Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        if (e.dataTransfer.files.length) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFileSelect(fileInput.files[0]);
        }
    });

    function handleFileSelect(file) {
        currentFile = file;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
        selectedFileInfo.classList.remove('hidden');
        btnStart.removeAttribute('disabled');
    }

    // Submit / Upload Form
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!currentFile) return;

        const formData = new FormData();
        formData.append('video', currentFile);
        formData.append('view', document.getElementById('cameraView').value);
        formData.append('mode', document.getElementById('analysisMode').value);
        formData.append('auto_drive_sync', document.getElementById('autoDriveSync').checked);

        // UI state -> uploading & processing
        btnStart.setAttribute('disabled', 'true');
        processingSection.classList.remove('hidden');
        resultsSection.classList.add('hidden');
        progressBarFill.style.width = '10%';
        statusMessage.textContent = 'Uploading video file...';
        statusPercent.textContent = '10%';

        try {
            const resp = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Upload failed');
            }

            const data = await resp.json();
            const jobId = data.job_id;
            
            // Start polling progress
            startPolling(jobId);

        } catch (error) {
            alert('Upload error: ' + error.message);
            btnStart.removeAttribute('disabled');
            processingSection.classList.add('hidden');
        }
    });

    function startPolling(jobId) {
        if (pollInterval) clearInterval(pollInterval);

        pollInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/jobs/${jobId}`);
                if (!resp.ok) return;

                const job = await resp.json();

                if (job.status === 'processing') {
                    const percent = Math.min(95, Math.max(20, job.progress || 20));
                    progressBarFill.style.width = `${percent}%`;
                    statusPercent.textContent = `${percent}%`;
                    statusMessage.textContent = job.message || 'Analyzing bowler biomechanics...';
                } else if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    progressBarFill.style.width = '100%';
                    statusPercent.textContent = '100%';
                    statusMessage.textContent = 'Analysis complete!';

                    setTimeout(() => {
                        processingSection.classList.add('hidden');
                        displayResults(job);
                        btnStart.removeAttribute('disabled');
                    }, 500);

                } else if (job.status === 'error') {
                    clearInterval(pollInterval);
                    alert('Processing error: ' + job.error);
                    processingSection.classList.add('hidden');
                    btnStart.removeAttribute('disabled');
                }
            } catch (err) {
                console.error('Polling error', err);
            }
        }, 1500);
    }

    function displayResults(job) {
        resultsSection.classList.remove('hidden');

        // Populate summary cards
        const summary = job.summary || {};
        document.getElementById('valReleaseVel').textContent = summary.peak_release_velocity_px_s 
            ? Math.round(summary.peak_release_velocity_px_s) 
            : '--';
        document.getElementById('valSpineTilt').textContent = summary.spine_tilt_at_release_deg != null 
            ? summary.spine_tilt_at_release_deg.toFixed(1) + '°' 
            : '--';
        document.getElementById('valKneeFlex').textContent = summary.knee_flexion_at_release_deg != null 
            ? summary.knee_flexion_at_release_deg.toFixed(1) + '°' 
            : '--';
        document.getElementById('valFrames').textContent = job.frame_count || '--';

        // Video Player
        if (job.annotated_video_url) {
            const videoElem = document.getElementById('resultVideo');
            videoElem.src = job.annotated_video_url;
            videoElem.load();
            document.getElementById('btnDownloadVideo').href = job.annotated_video_url;
        }

        // Google Drive Banner
        const driveBanner = document.getElementById('driveResultBanner');
        if (job.gdrive_sync && job.gdrive_sync.web_view_link) {
            driveBanner.classList.remove('hidden');
            document.getElementById('driveResultLink').href = job.gdrive_sync.web_view_link;
        } else {
            driveBanner.classList.add('hidden');
        }

        // Biomechanics Chart
        if (job.history && job.history.length > 0) {
            renderChart(job.history);
        }

        // Bowling Scorecard
        const scorecardCard = document.getElementById('scorecardCard');
        if (job.game_summary) {
            scorecardCard.classList.remove('hidden');
            renderScorecard(job.game_summary);
        } else {
            scorecardCard.classList.add('hidden');
        }
    }

    function renderScorecard(game) {
        const totalElem = document.getElementById('scorecardTotal');
        const rollsRow = document.getElementById('scorecardRollsRow');
        const cumRow = document.getElementById('scorecardCumRow');
        const noteElem = document.getElementById('scorecardNote');

        if (game.total_score != null) {
            totalElem.textContent = game.total_score;
        } else if (game.rolls && game.rolls.length > 0) {
            totalElem.textContent = game.rolls.reduce((a, b) => a + b, 0) + ' (partial)';
        } else {
            totalElem.textContent = '--';
        }

        if (game.note) {
            noteElem.textContent = 'ℹ️ ' + game.note;
            noteElem.classList.remove('hidden');
        } else {
            noteElem.classList.add('hidden');
        }

        rollsRow.innerHTML = '';
        cumRow.innerHTML = '';

        const frames = game.frames || [];
        for (let i = 1; i <= 10; i++) {
            const frame = frames.find(f => f.frame_number === i);
            const rollCell = document.createElement('td');
            const cumCell = document.createElement('td');

            if (frame) {
                let rollsText = '';
                if (frame.is_strike) {
                    rollsText = '<span class="strike">X</span>';
                } else if (frame.is_spare) {
                    rollsText = `${frame.rolls[0]} <span class="spare">/</span>`;
                } else {
                    rollsText = frame.rolls.join(' ');
                }
                rollCell.innerHTML = `<div class="roll-box">${rollsText}</div>`;
                cumCell.innerHTML = `<div class="cum-box">${frame.cumulative_score}</div>`;
            } else {
                rollCell.innerHTML = '<div class="roll-box empty">-</div>';
                cumCell.innerHTML = '<div class="cum-box empty">-</div>';
            }

            rollsRow.appendChild(rollCell);
            cumRow.appendChild(cumCell);
        }
    }

    function renderChart(history) {
        const ctx = document.getElementById('biomechanicsChart').getContext('2d');
        const labels = history.map((_, idx) => `Frame ${idx + 1}`);
        const velocities = history.map(h => h.ball_velocity_px_s || 0);
        const spineTilts = history.map(h => h.spine_tilt_deg || null);

        if (biomechanicsChart) {
            biomechanicsChart.destroy();
        }

        biomechanicsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Ball Velocity (px/s)',
                        data: velocities,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.3,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Spine Tilt (°)',
                        data: spineTilts,
                        borderColor: '#10b981',
                        borderDash: [4, 4],
                        tension: 0.3,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: {
                        ticks: { color: '#8b9bb4', maxTicksLimit: 12 },
                        grid: { color: '#263445' }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        ticks: { color: '#3b82f6' },
                        grid: { color: '#263445' },
                        title: { display: true, text: 'Velocity (px/s)', color: '#3b82f6' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#10b981' },
                        title: { display: true, text: 'Spine Tilt (°)', color: '#10b981' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#f0f4f8' }
                    }
                }
            }
        });
    }

    // Modal Events
    btnOpenDrive.addEventListener('click', () => driveModal.classList.remove('hidden'));
    btnCloseDrive.addEventListener('click', () => driveModal.classList.add('hidden'));
    btnCancelDrive.addEventListener('click', () => driveModal.classList.add('hidden'));

    driveSettingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const folderId = document.getElementById('driveFolderId').value;
        const enabled = document.getElementById('driveEnabled').checked;
        const jsonFileInput = document.getElementById('saJsonFile');

        const formData = new FormData();
        formData.append('folder_id', folderId);
        formData.append('enabled', enabled);
        if (jsonFileInput.files.length) {
            formData.append('sa_json', jsonFileInput.files[0]);
        }

        try {
            const resp = await fetch('/api/settings/gdrive', {
                method: 'POST',
                body: formData
            });

            if (resp.ok) {
                alert('Google Drive settings updated successfully!');
                driveModal.classList.add('hidden');
            } else {
                alert('Failed to save settings');
            }
        } catch (err) {
            alert('Error saving Drive settings: ' + err.message);
        }
    });
});
