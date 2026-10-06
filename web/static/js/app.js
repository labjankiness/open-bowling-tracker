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

    // Load saved bowler profile from localStorage if available
    const savedHandedness = localStorage.getItem('bowlerHandedness');
    const savedStyle = localStorage.getItem('deliveryStyle');
    const savedBall = localStorage.getItem('bowlingBall');
    const handednessSelect = document.getElementById('bowlerHandedness');
    const styleSelect = document.getElementById('deliveryStyle');

    if (savedHandedness && handednessSelect) {
        handednessSelect.value = savedHandedness;
    }
    if (savedStyle && styleSelect) {
        styleSelect.value = savedStyle;
    }

    if (handednessSelect) {
        handednessSelect.addEventListener('change', (e) => {
            localStorage.setItem('bowlerHandedness', e.target.value);
        });
    }
    if (styleSelect) {
        styleSelect.addEventListener('change', (e) => {
            localStorage.setItem('deliveryStyle', e.target.value);
        });
    }

    // Searchable Bowling Ball Combobox Controller
    const ballPickerTrigger = document.getElementById('ballPickerTrigger');
    const ballDropdownMenu = document.getElementById('ballDropdownMenu');
    const ballSearchFilter = document.getElementById('ballSearchFilter');
    const ballOptionsList = document.getElementById('ballOptionsList');
    const ballTriggerText = document.getElementById('ballTriggerText');
    const ballHiddenInput = document.getElementById('bowlingBall');

    function selectBallOption(val, text) {
        if (ballHiddenInput) ballHiddenInput.value = val;
        if (ballTriggerText) ballTriggerText.textContent = text;
        localStorage.setItem('bowlingBall', val);
        localStorage.setItem('bowlingBallText', text);

        if (ballOptionsList) {
            ballOptionsList.querySelectorAll('.ball-option-item').forEach(item => {
                if (item.getAttribute('data-value') === val) {
                    item.classList.add('selected');
                } else {
                    item.classList.remove('selected');
                }
            });
        }
        if (ballDropdownMenu) ballDropdownMenu.classList.add('hidden');
    }

    if (savedBall && ballHiddenInput) {
        const savedText = localStorage.getItem('bowlingBallText') || '✨ Auto-Detect (Ball Color & Core)';
        selectBallOption(savedBall, savedText);
    }

    if (ballPickerTrigger && ballDropdownMenu) {
        ballPickerTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            ballDropdownMenu.classList.toggle('hidden');
            if (!ballDropdownMenu.classList.contains('hidden') && ballSearchFilter) {
                ballSearchFilter.value = '';
                filterBallOptions('');
                ballSearchFilter.focus();
            }
        });
    }

    function filterBallOptions(query) {
        if (!ballOptionsList) return;
        const q = query.toLowerCase().trim();
        const items = ballOptionsList.querySelectorAll('.ball-option-item');
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (!q || text.includes(q)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    if (ballSearchFilter) {
        ballSearchFilter.addEventListener('input', (e) => {
            filterBallOptions(e.target.value);
        });
        ballSearchFilter.addEventListener('click', (e) => e.stopPropagation());
    }

    if (ballOptionsList) {
        ballOptionsList.addEventListener('click', (e) => {
            const item = e.target.closest('.ball-option-item');
            if (item) {
                const val = item.getAttribute('data-value');
                const title = item.querySelector('.ball-opt-main') ? item.querySelector('.ball-opt-main').textContent : item.textContent;
                selectBallOption(val, title);
            }
        });
    }

    // Dismiss dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (ballDropdownMenu && !ballDropdownMenu.contains(e.target) && e.target !== ballPickerTrigger) {
            ballDropdownMenu.classList.add('hidden');
        }
    });

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
        formData.append('bowling_ball', document.getElementById('bowlingBall') ? document.getElementById('bowlingBall').value : 'auto');
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

        const phases = summary.approach_phases;
        const valTimingRatio = document.getElementById('valTimingRatio');
        const valBalanceScore = document.getElementById('valBalanceScore');
        if (phases) {
            if (valTimingRatio) valTimingRatio.textContent = phases.timing_ratio != null ? phases.timing_ratio.toFixed(2) : '--';
            if (valBalanceScore) valBalanceScore.textContent = phases.balance_score != null ? `${phases.balance_score}/100` : '--';
        } else {
            if (valTimingRatio) valTimingRatio.textContent = '--';
            if (valBalanceScore) valBalanceScore.textContent = '--';
        }

        // Footwork Drift & Bowling Ball
        const valDrift = document.getElementById('valLateralDrift');
        if (valDrift) {
            valDrift.textContent = summary.lateral_drift_boards != null 
                ? (summary.lateral_drift_boards > 0 ? `+${summary.lateral_drift_boards}` : `${summary.lateral_drift_boards}`)
                : '0.0';
        }

        const valBall = document.getElementById('valBowlingBall');
        const valReaction = document.getElementById('valBallReactionShape');
        if (summary.bowling_ball) {
            if (valBall) valBall.textContent = summary.bowling_ball.name || 'Standard Ball';
            if (valReaction) valReaction.textContent = `${summary.bowling_ball.reaction_shape || 'Benchmark'} (${summary.bowling_ball.detection_mode || ''})`;
        } else {
            if (valBall) valBall.textContent = 'Generic Reactive';
            if (valReaction) valReaction.textContent = 'Standard Cover';
        }

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

        // Video Player & Phase Scrubber
        const videoElem = document.getElementById('resultVideo');
        if (job.annotated_video_url) {
            videoElem.src = job.annotated_video_url;
            videoElem.load();
            videoElem.play().catch(e => console.log('Autoplay deferred:', e));
            document.getElementById('btnDownloadVideo').href = job.annotated_video_url;
        }

        // Setup Phase Timeline Scrubber
        const phaseContainer = document.getElementById('phaseTimelineContainer');
        if (phases && phaseContainer) {
            phaseContainer.classList.remove('hidden');

            const bindPhaseBtn = (btnId, stampId, timeVal) => {
                const btn = document.getElementById(btnId);
                const stamp = document.getElementById(stampId);
                if (btn && timeVal != null) {
                    btn.setAttribute('data-time', timeVal);
                    if (stamp) stamp.textContent = `${timeVal.toFixed(1)}s`;
                    btn.onclick = () => {
                        if (videoElem) {
                            videoElem.currentTime = timeVal;
                            videoElem.play().catch(() => {});
                        }
                    };
                }
            };

            bindPhaseBtn('btnPhasePushaway', 'stampPushaway', phases.pushaway_time_s);
            bindPhaseBtn('btnPhaseApex', 'stampApex', phases.apex_time_s);
            bindPhaseBtn('btnPhasePowerStep', 'stampPowerStep', phases.power_step_time_s);
            bindPhaseBtn('btnPhaseRelease', 'stampRelease', phases.release_time_s);
            bindPhaseBtn('btnPhaseFinish', 'stampFinish', phases.finish_time_s);
        } else if (phaseContainer) {
            phaseContainer.classList.add('hidden');
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

        // Pin Leave Annotation
        const pinLeaveTag = document.getElementById('pinLeaveTag');
        if (pinLeaveTag && game.rolls && game.rolls.length > 0) {
            const firstRoll = game.rolls[0];
            const standing = Math.max(0, 10 - firstRoll);
            if (firstRoll === 10) {
                pinLeaveTag.textContent = 'Strike (0 pins standing)';
            } else if (standing === 1) {
                pinLeaveTag.textContent = '1-Pin Leave (Corner or Pocket Spare)';
            } else if (standing === 2) {
                pinLeaveTag.textContent = '2-Pin Leave / Cluster';
            } else {
                pinLeaveTag.textContent = `${standing} Pins Standing on Deck`;
            }
        }

        // Initialize Manual Rolls Input
        const manualInput = document.getElementById('manualRollsInput');
        if (manualInput && game.rolls) {
            manualInput.value = game.rolls.join(', ');
        }
    }

    // Toggle Manual Score Drawer
    const btnToggleManualScore = document.getElementById('btnToggleManualScore');
    const manualScoreDrawer = document.getElementById('manualScoreDrawer');
    if (btnToggleManualScore && manualScoreDrawer) {
        btnToggleManualScore.addEventListener('click', () => {
            manualScoreDrawer.classList.toggle('hidden');
        });
    }

    // Apply Manual Score Override
    const btnApplyManualScore = document.getElementById('btnApplyManualScore');
    if (btnApplyManualScore) {
        btnApplyManualScore.addEventListener('click', () => {
            const inputVal = document.getElementById('manualRollsInput').value;
            const rolls = inputVal.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n >= 0 && n <= 10);
            if (rolls.length === 0) {
                alert('Please enter valid pin counts (0-10 separated by commas).');
                return;
            }

            // Calculate standard 10-pin score locally
            const simulatedFrames = [];
            let rIdx = 0;
            let cumScore = 0;

            for (let f = 1; f <= 10 && rIdx < rolls.length; f++) {
                const r1 = rolls[rIdx];
                if (f === 10) {
                    const r2 = rIdx + 1 < rolls.length ? rolls[rIdx + 1] : 0;
                    const r3 = rIdx + 2 < rolls.length ? rolls[rIdx + 2] : 0;
                    const fScore = r1 + r2 + r3;
                    cumScore += fScore;
                    simulatedFrames.push({
                        frame_number: 10,
                        rolls: [r1, r2, r3],
                        is_strike: (r1 === 10),
                        is_spare: (r1 < 10 && r1 + r2 === 10),
                        frame_score: fScore,
                        cumulative_score: cumScore
                    });
                    break;
                } else if (r1 === 10) {
                    const b1 = rIdx + 1 < rolls.length ? rolls[rIdx + 1] : 0;
                    const b2 = rIdx + 2 < rolls.length ? rolls[rIdx + 2] : 0;
                    cumScore += 10 + b1 + b2;
                    simulatedFrames.push({
                        frame_number: f,
                        rolls: [10],
                        is_strike: true,
                        is_spare: false,
                        frame_score: 10 + b1 + b2,
                        cumulative_score: cumScore
                    });
                    rIdx += 1;
                } else {
                    const r2 = rIdx + 1 < rolls.length ? rolls[rIdx + 1] : 0;
                    const isSpare = (r1 + r2 === 10);
                    const bonus = isSpare && rIdx + 2 < rolls.length ? rolls[rIdx + 2] : 0;
                    const fScore = r1 + r2 + bonus;
                    cumScore += fScore;
                    simulatedFrames.push({
                        frame_number: f,
                        rolls: [r1, r2],
                        is_strike: false,
                        is_spare: isSpare,
                        frame_score: fScore,
                        cumulative_score: cumScore
                    });
                    rIdx += 2;
                }
            }

            const updatedGame = {
                rolls: rolls,
                total_score: cumScore,
                frames: simulatedFrames,
                is_complete: simulatedFrames.length === 10
            };

            const scoreDetectionTag = document.getElementById('scoreDetectionTag');
            if (scoreDetectionTag) {
                scoreDetectionTag.textContent = '✏️ Manual User Override';
                scoreDetectionTag.className = 'badge badge-warning';
            }

            renderScorecard(updatedGame);
            manualScoreDrawer.classList.add('hidden');
        });
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

    // --- Multi-Source Cloud Pickers (OneDrive & Google Drive) ---
    const btnPickOneDrive = document.getElementById('btnPickOneDrive');
    const btnConfigOneDrive = document.getElementById('btnConfigOneDrive');
    const btnPickGDrive = document.getElementById('btnPickGDrive');
    const onedriveModal = document.getElementById('onedriveModal');
    const btnCloseOneDriveModal = document.getElementById('btnCloseOneDriveModal');
    const btnCancelOneDrive = document.getElementById('btnCancelOneDrive');
    const btnSaveOneDrive = document.getElementById('btnSaveOneDrive');
    const odClientIdInput = document.getElementById('odClientId');

    // Load saved OneDrive client ID from localStorage
    if (odClientIdInput) {
        odClientIdInput.value = localStorage.getItem('onedrive_client_id') || '';
    }

    if (btnConfigOneDrive && onedriveModal) {
        btnConfigOneDrive.addEventListener('click', () => {
            onedriveModal.classList.remove('hidden');
        });
    }

    if (btnCloseOneDriveModal && onedriveModal) {
        btnCloseOneDriveModal.addEventListener('click', () => onedriveModal.classList.add('hidden'));
    }

    if (btnCancelOneDrive && onedriveModal) {
        btnCancelOneDrive.addEventListener('click', () => onedriveModal.classList.add('hidden'));
    }

    if (btnSaveOneDrive && odClientIdInput && onedriveModal) {
        btnSaveOneDrive.addEventListener('click', () => {
            const cid = odClientIdInput.value.trim();
            localStorage.setItem('onedrive_client_id', cid);
            onedriveModal.classList.add('hidden');
            alert('OneDrive Client ID saved! You can now use the OneDrive button.');
        });
    }

    // Launch Microsoft OneDrive File Picker
    if (btnPickOneDrive) {
        btnPickOneDrive.addEventListener('click', () => {
            const clientId = localStorage.getItem('onedrive_client_id');
            if (!clientId) {
                if (onedriveModal) {
                    onedriveModal.classList.remove('hidden');
                    alert('Please enter your Microsoft Azure App Client ID to connect to OneDrive.');
                }
                return;
            }

            if (typeof OneDrive === 'undefined') {
                alert('OneDrive SDK is still loading. Please check your internet connection or try again in a few seconds.');
                return;
            }

            const odOptions = {
                clientId: clientId,
                action: 'download',
                multiSelect: false,
                advanced: {
                    filter: '.mp4,.mov,.m4v'
                },
                success: function(files) {
                    if (files && files.values && files.values.length > 0) {
                        const fileMeta = files.values[0];
                        const downloadUrl = fileMeta['@microsoft.graph.downloadUrl'];
                        const fileName = fileMeta.name;
                        
                        selectedFileName.textContent = `[OneDrive] ${fileName}`;
                        selectedFileSize.textContent = `${(fileMeta.size / (1024 * 1024)).toFixed(1)} MB`;
                        selectedFileInfo.classList.remove('hidden');
                        btnStart.removeAttribute('disabled');

                        // Fetch file blob from downloadUrl and prepare for uploadForm
                        statusMessage.textContent = 'Streaming file from OneDrive...';
                        fetch(downloadUrl)
                            .then(res => res.blob())
                            .then(blob => {
                                currentFile = new File([blob], fileName, { type: blob.type || 'video/mp4' });
                                console.log('OneDrive video loaded:', fileName, currentFile.size);
                            })
                            .catch(err => {
                                console.error('Error fetching OneDrive file:', err);
                                alert('Could not stream video directly from OneDrive: ' + err.message);
                            });
                    }
                },
                cancel: function() {
                    console.log('OneDrive picker cancelled by user');
                },
                error: function(e) {
                    console.error('OneDrive picker error:', e);
                    alert('OneDrive error: ' + (e.message || JSON.stringify(e)));
                }
            };

            OneDrive.open(odOptions);
        });
    }

    // Google Drive Picker Shortcut
    if (btnPickGDrive) {
        btnPickGDrive.addEventListener('click', () => {
            const libraryModal = document.getElementById('libraryModal');
            if (libraryModal) {
                libraryModal.classList.remove('hidden');
                loadLibrary();
                const tabDrive = document.getElementById('tabDrive');
                const libraryListDrive = document.getElementById('libraryListDrive');
                if (tabDrive && libraryListDrive) {
                    switchLibraryTab(tabDrive, libraryListDrive);
                }
            }
        });
    }

    // Dual-Shot Side-by-Side Comparison Modal
    const btnOpenCompareModal = document.getElementById('btnOpenCompareModal');
    const btnCloseCompareModal = document.getElementById('btnCloseCompareModal');
    const compareModal = document.getElementById('compareModal');
    const compareVideoA = document.getElementById('compareVideoA');
    const compareVideoB = document.getElementById('compareVideoB');
    const compareSelectSecondary = document.getElementById('compareSelectSecondary');
    const btnSyncPlay = document.getElementById('btnSyncPlay');
    const btnSyncRestart = document.getElementById('btnSyncRestart');
    const compareGhostOpacity = document.getElementById('compareGhostOpacity');

    if (btnOpenCompareModal && compareModal) {
        btnOpenCompareModal.addEventListener('click', async () => {
            compareModal.classList.remove('hidden');
            const mainVideo = document.getElementById('resultVideo');
            if (mainVideo && mainVideo.src) {
                compareVideoA.src = mainVideo.src;
                compareVideoA.currentTime = mainVideo.currentTime || 0;
            }

            // Populate secondary video options from library
            try {
                const resp = await fetch('/api/library');
                if (resp.ok) {
                    const data = await resp.json();
                    const allClips = [...(data.local_videos || []), ...(data.training_videos || [])];
                    compareSelectSecondary.innerHTML = '<option value="">Select a previous video from library...</option>';
                    allClips.forEach(v => {
                        const opt = document.createElement('option');
                        opt.value = v.url;
                        opt.textContent = `${v.name} (${v.size_mb} MB)`;
                        compareSelectSecondary.appendChild(opt);
                    });
                }
            } catch (err) {
                console.error('Error fetching library for comparison:', err);
            }
        });
    }

    if (btnCloseCompareModal && compareModal) {
        btnCloseCompareModal.addEventListener('click', () => {
            compareModal.classList.add('hidden');
            if (compareVideoA) compareVideoA.pause();
            if (compareVideoB) compareVideoB.pause();
        });
    }

    if (compareSelectSecondary && compareVideoB) {
        compareSelectSecondary.addEventListener('change', (e) => {
            if (e.target.value) {
                compareVideoB.src = e.target.value;
                compareVideoB.load();
            }
        });
    }

    if (btnSyncPlay && compareVideoA && compareVideoB) {
        btnSyncPlay.addEventListener('click', () => {
            if (compareVideoA.paused) {
                compareVideoA.play();
                compareVideoB.play();
                btnSyncPlay.textContent = '⏸ Pause Both';
            } else {
                compareVideoA.pause();
                compareVideoB.pause();
                btnSyncPlay.textContent = '▶️ Synchronized Play';
            }
        });
    }

    if (btnSyncRestart && compareVideoA && compareVideoB) {
        btnSyncRestart.addEventListener('click', () => {
            compareVideoA.currentTime = 0;
            compareVideoB.currentTime = 0;
        });
    }

    if (compareGhostOpacity && compareVideoB) {
        compareGhostOpacity.addEventListener('input', (e) => {
            const val = e.target.value / 100;
            compareVideoB.style.opacity = val;
        });
    }
});

