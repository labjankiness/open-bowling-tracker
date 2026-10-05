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
        formData.append('handedness', document.getElementById('bowlerHandedness').value);
        formData.append('style', document.getElementById('deliveryStyle').value);
        formData.append('speed_factor', document.getElementById('videoSpeed') ? document.getElementById('videoSpeed').value : 'auto');
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
        document.getElementById('valBallSpeed').textContent = summary.ball_speed_mph != null 
            ? summary.ball_speed_mph 
            : '--';
        document.getElementById('valBallRpm').textContent = summary.ball_rotation_rpm != null 
            ? summary.ball_rotation_rpm 
            : '--';
        document.getElementById('valLaunchPoint').textContent = summary.launch_point_board || '--';
        document.getElementById('valBreakpoint').textContent = summary.breakpoint || '--';
        document.getElementById('valSpineTilt').textContent = summary.spine_tilt_at_release_deg != null 
            ? summary.spine_tilt_at_release_deg.toFixed(1) + '°' 
            : '--';
        document.getElementById('valKneeFlex').textContent = summary.knee_flexion_at_release_deg != null 
            ? summary.knee_flexion_at_release_deg.toFixed(1) + '°' 
            : '--';

        // AI Bowling Coach Breakdown
        const coachSection = document.getElementById('coachAdviceSection');
        const coachList = document.getElementById('coachAdviceList');
        if (job.coach_advice && job.coach_advice.length > 0) {
            coachSection.classList.remove('hidden');
            coachList.innerHTML = '';
            job.coach_advice.forEach(tip => {
                const card = document.createElement('div');
                card.className = `coach-card badge-${tip.badge || 'info'}`;
                card.innerHTML = `
                    <div class="coach-card-top">
                        <span class="coach-cat">${tip.category}</span>
                        <span class="coach-status">${tip.status}</span>
                    </div>
                    <p class="coach-msg">${tip.message}</p>
                `;
                coachList.appendChild(card);
            });
        } else {
            coachSection.classList.add('hidden');
        }

        // Video Player
        if (job.annotated_video_url) {
            const videoElem = document.getElementById('resultVideo');
            videoElem.src = job.annotated_video_url;
            videoElem.load();
            videoElem.play().catch(e => console.log('Autoplay deferred:', e));
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

    // Library Modal
    const btnOpenLibrary = document.getElementById('btnOpenLibrary');
    const btnCloseLibrary = document.getElementById('btnCloseLibraryModal');
    const libraryModal = document.getElementById('libraryModal');
    const tabTraining = document.getElementById('tabTraining');
    const tabLocal = document.getElementById('tabLocal');
    const tabDrive = document.getElementById('tabDrive');
    const libraryListTraining = document.getElementById('libraryListTraining');
    const libraryListLocal = document.getElementById('libraryListLocal');
    const libraryListDrive = document.getElementById('libraryListDrive');

    if (btnOpenLibrary) {
        btnOpenLibrary.addEventListener('click', () => {
            libraryModal.classList.remove('hidden');
            loadLibrary();
        });
    }

    if (btnCloseLibrary) {
        btnCloseLibrary.addEventListener('click', () => libraryModal.classList.add('hidden'));
    }

    function switchLibraryTab(activeTab, activeList) {
        [tabTraining, tabLocal, tabDrive].forEach(t => { if (t) t.classList.remove('active'); });
        [libraryListTraining, libraryListLocal, libraryListDrive].forEach(l => { if (l) l.classList.add('hidden'); });

        if (activeTab) activeTab.classList.add('active');
        if (activeList) activeList.classList.remove('hidden');
    }

    if (tabTraining) {
        tabTraining.addEventListener('click', () => switchLibraryTab(tabTraining, libraryListTraining));
    }
    if (tabLocal) {
        tabLocal.addEventListener('click', () => switchLibraryTab(tabLocal, libraryListLocal));
    }
    if (tabDrive) {
        tabDrive.addEventListener('click', () => switchLibraryTab(tabDrive, libraryListDrive));
    }

    async function analyzeTrainingVideo(filename) {
        libraryModal.classList.add('hidden');
        btnStart.setAttribute('disabled', 'true');
        processingSection.classList.remove('hidden');
        resultsSection.classList.add('hidden');
        progressBarFill.style.width = '10%';
        statusMessage.textContent = `Queuing ${filename} from training drive...`;
        statusPercent.textContent = '10%';

        const formData = new FormData();
        formData.append('filename', filename);
        formData.append('view', document.getElementById('cameraView').value);
        formData.append('handedness', document.getElementById('bowlerHandedness').value);
        formData.append('style', document.getElementById('deliveryStyle').value);
        formData.append('speed_factor', document.getElementById('videoSpeed') ? document.getElementById('videoSpeed').value : 'auto');
        formData.append('mode', document.getElementById('analysisMode').value);
        formData.append('auto_drive_sync', document.getElementById('autoDriveSync').checked);

        try {
            const resp = await fetch('/api/analyze-training-video', {
                method: 'POST',
                body: formData
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Analysis request failed');
            }

            const data = await resp.json();
            startPolling(data.job_id);
        } catch (err) {
            alert('Error starting analysis: ' + err.message);
            btnStart.removeAttribute('disabled');
            processingSection.classList.add('hidden');
        }
    }

    async function loadLibrary() {
        try {
            const resp = await fetch('/api/library');
            if (!resp.ok) return;
            const data = await resp.json();

            if (document.getElementById('countTraining')) {
                document.getElementById('countTraining').textContent = (data.training_videos || []).length;
            }
            if (document.getElementById('countLocal')) {
                document.getElementById('countLocal').textContent = (data.local_videos || []).length;
            }
            if (document.getElementById('countDrive')) {
                document.getElementById('countDrive').textContent = (data.gdrive_videos || []).length;
            }

            // 1. Render Training Drive Clips
            if (libraryListTraining) {
                libraryListTraining.innerHTML = '';
                const trainingList = data.training_videos || [];
                if (trainingList.length === 0) {
                    libraryListTraining.innerHTML = '<p class="empty-msg">No videos found in the connected training drive.</p>';
                } else {
                    trainingList.forEach(vid => {
                        const meta = vid.metadata || {};
                        const dateStr = meta.date || 'Unknown Date';
                        const timeStr = meta.time || '';
                        const durStr = meta.duration_str || '';
                        const resStr = meta.resolution || '';
                        const loc = meta.location;

                        let locationBadge = '';
                        if (loc && loc.maps_url) {
                            locationBadge = `<a href="${loc.maps_url}" target="_blank" class="lib-meta-tag loc-tag" title="Open GPS Location in Google Maps">📍 ${loc.formatted}</a>`;
                        }

                        const item = document.createElement('div');
                        item.className = 'library-card';
                        item.innerHTML = `
                            <div class="lib-card-left">
                                <div class="lib-thumb-wrapper">
                                    <img src="${vid.thumbnail_url}" class="lib-thumb" loading="lazy" alt="Preview" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                                    <div class="lib-thumb-placeholder" style="display:none;">🎳</div>
                                    ${durStr ? `<span class="thumb-duration-badge">${durStr}</span>` : ''}
                                </div>
                            </div>
                            <div class="lib-card-body">
                                <div class="lib-card-title" title="${vid.name}">${vid.name}</div>
                                <div class="lib-meta-row">
                                    <span class="lib-meta-tag">📅 ${dateStr} ${timeStr}</span>
                                    <span class="lib-meta-tag">💾 ${vid.size_mb} MB</span>
                                    ${resStr ? `<span class="lib-meta-tag">🎥 ${resStr}</span>` : ''}
                                </div>
                                ${locationBadge ? `<div class="lib-location-row">${locationBadge}</div>` : ''}
                            </div>
                            <div class="lib-card-actions">
                                <button class="btn btn-sm btn-primary btn-analyze-training" data-filename="${vid.name}" title="Analyze mechanics & compute metrics">⚡ Analyze</button>
                                <button class="btn btn-sm btn-outline btn-play-lib" data-url="${vid.url}" title="Play in Player">▶️ Play</button>
                                <a href="${vid.url}" download class="btn btn-sm btn-ghost" title="Download video file">⬇️</a>
                            </div>
                        `;
                        libraryListTraining.appendChild(item);
                    });

                    libraryListTraining.querySelectorAll('.btn-analyze-training').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const filename = e.currentTarget.getAttribute('data-filename');
                            analyzeTrainingVideo(filename);
                        });
                    });
                }
            }

            // 2. Render Processed Local Videos
            if (libraryListLocal) {
                libraryListLocal.innerHTML = '';
                const localList = data.local_videos || [];
                if (localList.length === 0) {
                    libraryListLocal.innerHTML = '<p class="empty-msg">No processed videos yet. Upload a clip above!</p>';
                } else {
                    localList.forEach(vid => {
                        const meta = vid.metadata || {};
                        const dateStr = meta.date || 'Unknown Date';
                        const timeStr = meta.time || '';
                        const durStr = meta.duration_str || '';
                        const resStr = meta.resolution || '';
                        const loc = meta.location;

                        let locationBadge = '';
                        if (loc && loc.maps_url) {
                            locationBadge = `<a href="${loc.maps_url}" target="_blank" class="lib-meta-tag loc-tag" title="Open GPS Location in Google Maps">📍 ${loc.formatted}</a>`;
                        }

                        const item = document.createElement('div');
                        item.className = 'library-card';
                        item.innerHTML = `
                            <div class="lib-card-left">
                                <div class="lib-thumb-wrapper">
                                    <img src="${vid.thumbnail_url}" class="lib-thumb" loading="lazy" alt="Preview" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                                    <div class="lib-thumb-placeholder" style="display:none;">📹</div>
                                    ${durStr ? `<span class="thumb-duration-badge">${durStr}</span>` : ''}
                                </div>
                            </div>
                            <div class="lib-card-body">
                                <div class="lib-card-title" title="${vid.name}">${vid.name}</div>
                                <div class="lib-meta-row">
                                    <span class="lib-meta-tag badge-annotated">🎯 AI Annotated</span>
                                    <span class="lib-meta-tag">📅 ${dateStr} ${timeStr}</span>
                                    <span class="lib-meta-tag">💾 ${vid.size_mb} MB</span>
                                    ${resStr ? `<span class="lib-meta-tag">🎥 ${resStr}</span>` : ''}
                                </div>
                                ${locationBadge ? `<div class="lib-location-row">${locationBadge}</div>` : ''}
                            </div>
                            <div class="lib-card-actions">
                                <button class="btn btn-sm btn-primary btn-play-lib" data-url="${vid.url}">▶️ Play in Player</button>
                                <a href="${vid.url}" download class="btn btn-sm btn-ghost" title="Download annotated video">⬇️</a>
                            </div>
                        `;
                        libraryListLocal.appendChild(item);
                    });
                }
            }

            // Common play button handler
            document.querySelectorAll('.btn-play-lib').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const url = e.currentTarget.getAttribute('data-url');
                    const videoElem = document.getElementById('resultVideo');
                    resultsSection.classList.remove('hidden');
                    videoElem.src = url;
                    videoElem.load();
                    videoElem.play().catch(err => console.log('Autoplay deferred:', err));
                    document.getElementById('btnDownloadVideo').href = url;
                    libraryModal.classList.add('hidden');
                    videoElem.scrollIntoView({ behavior: 'smooth' });
                });
            });

            // 3. Render Drive Videos
            if (libraryListDrive) {
                libraryListDrive.innerHTML = '';
                const driveList = data.gdrive_videos || [];
                if (driveList.length === 0) {
                    libraryListDrive.innerHTML = data.gdrive_configured 
                        ? '<p class="empty-msg">No videos found in your target Google Drive folder.</p>'
                        : '<p class="empty-msg">Google Drive sync is not configured yet. Click "Google Drive Sync" to connect!</p>';
                } else {
                    driveList.forEach(vid => {
                        const item = document.createElement('div');
                        item.className = 'library-card library-card-drive';
                        item.innerHTML = `
                            <div class="lib-card-left">
                                <div class="lib-thumb-wrapper lib-thumb-cloud">
                                    <span class="cloud-icon">☁️</span>
                                </div>
                            </div>
                            <div class="lib-card-body">
                                <div class="lib-card-title">${vid.name}</div>
                                <div class="lib-meta-row">
                                    <span class="lib-meta-tag">Google Drive Cloud File</span>
                                </div>
                            </div>
                            <div class="lib-card-actions">
                                <a href="${vid.webViewLink}" target="_blank" class="btn btn-sm btn-outline">View in Drive ↗</a>
                            </div>
                        `;
                        libraryListDrive.appendChild(item);
                    });
                }
            }

        } catch (e) {
            console.error('Error loading library:', e);
        }
    }

    // --- Live Batch Annotation Progress Monitor ---
    const batchProgressBarFill = document.getElementById('batchProgressBarFill');
    const batchCountText = document.getElementById('batchCountText');
    const batchPercentText = document.getElementById('batchPercentText');
    const batchEtaText = document.getElementById('batchEtaText');
    const batchPulseDot = document.getElementById('batchPulseDot');
    const batchStatusBadge = document.getElementById('batchStatusBadge');
    const batchCurrentVideo = document.getElementById('batchCurrentVideo');
    const batchLatestShot = document.getElementById('batchLatestShot');
    const btnToggleBatch = document.getElementById('btnToggleBatch');
    const btnViewBatchLibrary = document.getElementById('btnViewBatchLibrary');

    let isBatchRunning = false;

    async function pollBatchStatus() {
        try {
            const resp = await fetch('/api/batch-status');
            if (!resp.ok) return;
            const data = await resp.json();

            isBatchRunning = data.is_running;

            // Update Progress Bar
            const pct = data.percent || 0;
            if (batchProgressBarFill) {
                batchProgressBarFill.style.width = `${pct}%`;
            }
            if (batchPercentText) {
                batchPercentText.textContent = `${pct}%`;
            }
            if (batchCountText) {
                batchCountText.textContent = `${data.annotated_count || 0} / ${data.total_training || 0} Videos Annotated`;
            }

            // Update ETA
            if (batchEtaText) {
                const remaining = Math.max(0, (data.total_training || 0) - (data.annotated_count || 0));
                if (!data.is_running && pct < 100) {
                    batchEtaText.textContent = `⏱ Paused (${remaining} left)`;
                } else if (remaining === 0 || pct >= 100) {
                    batchEtaText.textContent = `⏱ Complete!`;
                } else {
                    const estMinutes = Math.ceil((remaining * 35) / 60);
                    if (estMinutes > 60) {
                        const hrs = (estMinutes / 60).toFixed(1);
                        batchEtaText.textContent = `⏱ Est. Remaining: ~${hrs} hrs`;
                    } else {
                        batchEtaText.textContent = `⏱ Est. Remaining: ~${estMinutes} mins`;
                    }
                }
            }

            // Update Badge & Pulse Dot
            if (data.is_running) {
                if (batchPulseDot) batchPulseDot.textContent = '🟢';
                if (batchStatusBadge) {
                    batchStatusBadge.textContent = 'Processing in Background';
                    batchStatusBadge.className = 'batch-badge active';
                }
                if (btnToggleBatch) {
                    btnToggleBatch.textContent = '⏸ Pause';
                    btnToggleBatch.className = 'btn btn-sm btn-outline';
                }
            } else if (pct >= 100) {
                if (batchPulseDot) batchPulseDot.textContent = '🎉';
                if (batchStatusBadge) {
                    batchStatusBadge.textContent = 'All Videos Completed';
                    batchStatusBadge.className = 'batch-badge completed';
                }
                if (btnToggleBatch) {
                    btnToggleBatch.textContent = '🔄 Re-Scan';
                    btnToggleBatch.className = 'btn btn-sm btn-outline';
                }
            } else {
                if (batchPulseDot) batchPulseDot.textContent = '🟡';
                if (batchStatusBadge) {
                    batchStatusBadge.textContent = 'Paused / Idle';
                    batchStatusBadge.className = 'batch-badge paused';
                }
                if (btnToggleBatch) {
                    btnToggleBatch.textContent = '▶ Resume';
                    btnToggleBatch.className = 'btn btn-sm btn-primary';
                }
            }

            // Current Video
            if (batchCurrentVideo) {
                if (data.current_video) {
                    batchCurrentVideo.textContent = data.current_video;
                } else if (data.is_running) {
                    batchCurrentVideo.textContent = 'Annotating clips...';
                } else {
                    batchCurrentVideo.textContent = 'Idle';
                }
            }

            // Latest Shot Stats
            if (batchLatestShot) {
                if (data.latest_stats) {
                    const s = data.latest_stats;
                    batchLatestShot.textContent = `${s.speed_mph || '--'} mph • ${s.rpm || '--'} RPM • Knee: ${s.knee_deg || '--'}° • Spine: ${s.spine_deg || '--'}°`;
                } else if (data.latest_annotated) {
                    batchLatestShot.textContent = `${data.latest_annotated.name} (${data.latest_annotated.size_mb} MB)`;
                } else {
                    batchLatestShot.textContent = '--';
                }
            }

        } catch (e) {
            console.error('Error polling batch status:', e);
        }
    }

    // Toggle Start / Stop Batch
    if (btnToggleBatch) {
        btnToggleBatch.addEventListener('click', async () => {
            btnToggleBatch.setAttribute('disabled', 'true');
            try {
                const endpoint = isBatchRunning ? '/api/batch-annotate/stop' : '/api/batch-annotate/start';
                await fetch(endpoint, { method: 'POST' });
                await pollBatchStatus();
            } catch (err) {
                console.error('Error toggling batch:', err);
            } finally {
                btnToggleBatch.removeAttribute('disabled');
            }
        });
    }

    // View in Library Button
    if (btnViewBatchLibrary) {
        btnViewBatchLibrary.addEventListener('click', () => {
            const libraryModal = document.getElementById('libraryModal');
            if (libraryModal) {
                libraryModal.classList.remove('hidden');
                loadLibrary();
                // Switch to Local / Processed tab
                const tabLocal = document.getElementById('tabLocal');
                const libraryListLocal = document.getElementById('libraryListLocal');
                if (tabLocal && libraryListLocal) {
                    switchLibraryTab(tabLocal, libraryListLocal);
                }
            }
        });
    }

    // Poll batch status every 2.5 seconds
    pollBatchStatus();
    setInterval(pollBatchStatus, 2500);
});
