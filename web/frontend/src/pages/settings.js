export function mount(root) {
  root.innerHTML = `
            <div class="page-header">
                <h1 class="greeting">Settings</h1>
                <p class="greeting-sub">Manage your account and preferences</p>
            </div><!-- Two Column Settings Layout -->
            <div class="settings-grid">
                <!-- Left Column: Account & Appearance -->
                <div>
                    <section class="settings-section">
                        <div class="card">
                            <h2 class="settings-title">Account Information</h2>
                            <p class="settings-desc">Update your personal information</p>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                                <div class="form-group" style="margin-bottom: 0;"><label class="form-label">First Name</label><input type="text" class="form-input" value=""></div>
                                <div class="form-group" style="margin-bottom: 0;"><label class="form-label">Last Name</label><input type="text" class="form-input" value="Johnson"></div>
                            </div>
                            <div class="form-group"><label class="form-label">Email Address</label><input type="email" class="form-input" value="alex.johnson@company.com"></div>
                            <div class="form-group"><label class="form-label">Job Title</label><input type="text" class="form-input" value="Product Manager"></div>
                            <div class="form-group" style="margin-bottom: 0;"><label class="form-label">Bio</label><textarea class="form-input" style="min-height: 80px; resize: vertical;">Product manager with 5+ years of experience in SaaS.</textarea></div>
                            <div style="margin-top: 1.25rem;"><button class="btn btn-primary">Save Changes</button></div>
                        </div>
                    </section>

                    <section class="settings-section">
                        <div class="card">
                            <h2 class="settings-title">Appearance</h2>
                            <p class="settings-desc">Customize how the dashboard looks</p>
                            <div class="settings-row">
                                <div class="settings-row-info"><div class="settings-row-label">Theme Mode</div><div class="settings-row-desc">Snow (light) or Carbon (dark)</div></div>
                                <div class="theme-toggle">
                                    <button class="theme-btn theme-btn-light active" onclick="setTheme('light')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg></button>
                                    <button class="theme-btn theme-btn-dark" onclick="setTheme('dark')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg></button>
                                </div>
                            </div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Compact Mode</div><div class="settings-row-desc">Reduce spacing throughout</div></div><label class="toggle"><input type="checkbox" id="compact-mode"><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Show Animations</div><div class="settings-row-desc">Enable smooth transitions</div></div><label class="toggle"><input type="checkbox" id="animations" checked=""><span class="toggle-slider"></span></label></div>
                        </div>
                    </section>
                </div>

                <!-- Right Column: Notifications & Security -->
                <div>
                    <section class="settings-section">
                        <div class="card">
                            <h2 class="settings-title">Notifications</h2>
                            <p class="settings-desc">Choose what notifications you receive</p>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Email Notifications</div><div class="settings-row-desc">Receive updates via email</div></div><label class="toggle"><input type="checkbox" id="email-notif" checked=""><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Push Notifications</div><div class="settings-row-desc">Real-time browser alerts</div></div><label class="toggle"><input type="checkbox" id="push-notif" checked=""><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Project Updates</div><div class="settings-row-desc">When projects are updated</div></div><label class="toggle"><input type="checkbox" id="project-notif" checked=""><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Team Mentions</div><div class="settings-row-desc">When someone mentions you</div></div><label class="toggle"><input type="checkbox" id="mention-notif" checked=""><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Weekly Digest</div><div class="settings-row-desc">Weekly activity summary</div></div><label class="toggle"><input type="checkbox" id="digest-notif"><span class="toggle-slider"></span></label></div>
                        </div>
                    </section>

                    <section class="settings-section">
                        <div class="card">
                            <h2 class="settings-title">Security</h2>
                            <p class="settings-desc">Manage account security</p>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Two-Factor Authentication</div><div class="settings-row-desc">Extra layer of security</div></div><label class="toggle"><input type="checkbox" id="two-factor"><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Login Alerts</div><div class="settings-row-desc">Notified of new logins</div></div><label class="toggle"><input type="checkbox" id="login-alerts" checked=""><span class="toggle-slider"></span></label></div>
                            <div class="settings-row"><div class="settings-row-info"><div class="settings-row-label">Session Timeout</div><div class="settings-row-desc">Auto logout after inactivity</div></div><select class="form-input" style="width: auto; min-width: 130px;"><option>15 minutes</option><option selected="">30 minutes</option><option>1 hour</option><option>Never</option></select></div>
                            <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border-color);">
                                <h3 style="font-size: 0.9375rem; font-weight: 600; color: var(--text-primary); margin-bottom: 1rem;">Change Password</h3>
                                <div class="form-group"><label class="form-label">Current Password</label><input type="password" class="form-input" placeholder="Current password"></div>
                                <div class="form-group"><label class="form-label">New Password</label><input type="password" class="form-input" placeholder="New password"></div>
                                <button class="btn btn-primary">Update Password</button>
                            </div>
                            <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--border-color);">
                                <h3 style="font-size: 0.9375rem; font-weight: 600; color: var(--danger); margin-bottom: 0.5rem;">Danger Zone</h3>
                                <button class="btn" style="background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid var(--danger);">Delete Account</button>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        `
  return { start() {}, destroy() {} }
}
