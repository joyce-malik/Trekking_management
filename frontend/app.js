const { createApp } = Vue;

createApp({
    data() {
        return {
            isRegistering: false,
            email: '', password: '', errorMessage: '', successMessage: '',
            reg: { name: '', email: '', password: '', phone: '', city: '' },
            token: localStorage.getItem('access_token') || null,
            role: localStorage.getItem('role') || null,
            treks: [],
            newTrek: { name: '', location: '', difficulty: '', duration: '', total_capacity: '', start_date: '', end_date: '' }
        }
    },
    mounted() {
        if (this.token) this.fetchTreks();
    },
    methods: {
        async login() {
            const res = await fetch('http://127.0.0.1:5000/api/login', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: this.email, password: this.password })
            });
            const data = await res.json();
            if (res.ok) {
                this.token = data.access_token; this.role = data.role;
                localStorage.setItem('access_token', this.token);
                localStorage.setItem('role', this.role);
                this.errorMessage = '';
                this.fetchTreks();
            } else this.errorMessage = data.msg;
        },
        async register() {
            const res = await fetch('http://127.0.0.1:5000/api/register', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.reg)
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = data.msg;
                this.isRegistering = false; // Switch back to login
                this.errorMessage = '';
            } else this.errorMessage = data.msg;
        },
        logout() {
            this.token = null; this.role = null; this.treks = [];
            localStorage.clear();
        },
        async fetchTreks() {
            const res = await fetch('http://127.0.0.1:5000/api/treks');
            this.treks = await res.json();
        },
        async createTrek() {
            await fetch('http://127.0.0.1:5000/api/treks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify(this.newTrek)
            });
            this.fetchTreks(); 
        },
        async bookTrek(trekId) {
            const res = await fetch(`http://127.0.0.1:5000/api/book/${trekId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            alert(data.msg);
            this.fetchTreks(); // Refresh slots
        },
        async exportHistory() {
            const res = await fetch('http://127.0.0.1:5000/api/export', {
                method: 'POST', headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            alert(data.msg + ". Task ID: " + data.task_id);
        }
    }
}).mount('#app');