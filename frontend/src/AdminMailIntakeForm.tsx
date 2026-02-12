import { useState } from 'react'
import { useParam } from 'react-router-dom'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001'

function AdminMailIntakeForm() {
    const mailboxId = useParam('mailboxId');
    const [date, setDate] = useState(Date.now());
    const [letterCount, setLetterCount] = useState(0);
    const [packageCount, setPackageCount] = useState(0);

    return (
        <div className="admin-mail-intake-form">
            <h2>Mail Intake Form for Mailbox {mailboxId}</h2>
            <form onSubmit={(e) => {
                e.preventDefault();
                fetch(`${API_BASE_URL}/mailboxes/${mailboxId}/intake`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        date,
                        letterCount,
                        packageCount,
                    }),
                }).then((response) => {
                    if (!response.ok) {
                        alert('Failed to submit mail intake');
                    } else {
                        alert('Mail intake submitted successfully');
                    }
                }).catch(() => {
                    alert('Failed to submit mail intake');
                });
            }}>
                <div>
                    <label>
                        Date:
                        <input
                            type="datetime-local"
                            value={new Date(date).toISOString().slice(0, 16)}
                            onChange={(e) => setDate(new Date(e.target.value).getTime())}
                            required
                        />
                    </label>
                </div>
                <div>
                    <label>
                        Letter Count:
                        <input
                            type="number"
                            value={letterCount}
                            onChange={(e) => setLetterCount(parseInt(e.target.value, 10))}
                            min="0"
                            required
                        />
                    </label>
                </div>
                <div>
                    <label>
                        Package Count:
                        <input
                            type="number"
                            value={packageCount}
                            onChange={(e) => setPackageCount(parseInt(e.target.value, 10))}
                            min="0"
                            required
                        />
                    </label>
                </div>
                <button type="submit">Submit</button>
            </form>
        </div>
    )
}

export default AdminMailIntakeForm;
