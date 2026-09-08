export function mount(root) {
  root.innerHTML = `
            <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h1 class="greeting">Inbox</h1>
                    <p class="greeting-sub">You have 3 unread messages</p>
                </div>
                <button class="btn btn-primary"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>Compose</button>
            </div>

            <!-- Inbox Split Pane -->
            <div class="inbox-container">
                <!-- Message List -->
                <div class="inbox-list">
                    <div class="inbox-header">
                        <div class="inbox-search" data-preference-region="">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                            <input type="text" name="messageSearch" placeholder="Search messages...">
                        </div>
                    </div>
                    <div class="message-list">
                        <div class="message-item active unread" onclick="selectMessage(this, 0)">
                            <div class="message-avatar">SC</div>
                            <div class="message-content">
                                <div class="message-header"><span class="message-sender">Sarah Chen</span><span class="message-time">9:45 AM</span></div>
                                <div class="message-subject">Project Update: Q1 Dashboard Redesign</div>
                                <div class="message-preview">Hi, I wanted to give you a quick update on the Q1 dashboard...</div>
                            </div>
                        </div>
                        <div class="message-item unread" onclick="selectMessage(this, 1)">
                            <div class="message-avatar" style="background: var(--success);">AB</div>
                            <div class="message-content">
                                <div class="message-header"><span class="message-sender">Analytics Bot</span><span class="message-time">8:00 AM</span></div>
                                <div class="message-subject">Weekly Analytics Report</div>
                                <div class="message-preview">Here's your weekly analytics summary for December 25-31...</div>
                            </div>
                        </div>
                        <div class="message-item unread" onclick="selectMessage(this, 2)">
                            <div class="message-avatar" style="background: #A855F7;">HR</div>
                            <div class="message-content">
                                <div class="message-header"><span class="message-sender">HR Team</span><span class="message-time">Yesterday</span></div>
                                <div class="message-subject">New Team Member Introduction</div>
                                <div class="message-preview">We're excited to announce that Michael Torres will be joining...</div>
                            </div>
                        </div>
                        <div class="message-item" onclick="selectMessage(this, 0)">
                            <div class="message-avatar" style="background: var(--warning);">MT</div>
                            <div class="message-content">
                                <div class="message-header"><span class="message-sender">Michael Torres</span><span class="message-time">Dec 30</span></div>
                                <div class="message-subject">Re: API Documentation Review</div>
                                <div class="message-preview">Thanks for the feedback! I've made the changes you suggested...</div>
                            </div>
                        </div>
                        <div class="message-item" onclick="selectMessage(this, 0)">
                            <div class="message-avatar" style="background: var(--success);">EW</div>
                            <div class="message-content">
                                <div class="message-header"><span class="message-sender">Emma Wilson</span><span class="message-time">Dec 29</span></div>
                                <div class="message-subject">Design Review Meeting Notes</div>
                                <div class="message-preview">Hi team, here are the notes from today's design review...</div>
                            </div>
                        </div>
                        <div class="message-item" onclick="selectMessage(this, 0)">
                            <div class="message-avatar" style="background: #A855F7;">JL</div>
                            <div class="message-content">
                                <div class="message-header"><span class="message-sender">James Lee</span><span class="message-time">Dec 28</span></div>
                                <div class="message-subject">Code Review: Authentication Module</div>
                                <div class="message-preview">I've completed the code review for the auth module. Overall looks...</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Message View -->
                <div class="message-view">
                    <div class="message-view-header">
                        <h2 class="message-view-subject">Project Update: Q1 Dashboard Redesign</h2>
                        <div class="message-view-meta">
                            <div class="message-view-sender">
                                <div class="message-avatar">SC</div>
                                <div><div class="message-view-sender-name">Sarah Chen</div><div class="message-view-sender-email">sarah.chen@company.com</div></div>
                            </div>
                            <div class="message-view-date">Jan 2, 2026 at 9:45 AM</div>
                        </div>
                    </div>
                    <div class="message-view-body">
                        <p>Hi,</p>
                        <p>I wanted to give you a quick update on the Q1 dashboard redesign project. We've completed the wireframes and initial mockups, and the team is ready to move into the development phase.</p>
                        <p>Key highlights from our progress:</p>
                        <p>• User research completed with 15 participants<br>• 3 design concepts presented to stakeholders<br>• Final direction approved by leadership<br>• Development sprint starting next Monday</p>
                        <p>Could we schedule a quick sync tomorrow to go over the technical requirements? Let me know what time works best for you.</p>
                        <p>Best regards,<br>Sarah</p>
                    </div>
                    <div class="message-view-reply">
                        <textarea class="reply-input" placeholder="Type your reply..."></textarea>
                        <div class="reply-actions">
                            <button class="btn btn-secondary"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>Attach</button>
                            <button class="btn btn-primary"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>Send Reply</button>
                        </div>
                    </div>
                </div>
            </div>
        `
  return { start() {}, destroy() {} }
}
