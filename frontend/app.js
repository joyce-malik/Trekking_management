const { createApp } = Vue;

createApp({
    data() {
        return {
            isRegistering: false,
            email: '', password: '', errorMessage: '', successMessage: '',
            reg: { name: '', email: '', password: '', phone: '', city: '' },
            token: localStorage.getItem('access_token') || null,
            role: localStorage.getItem('role') || null,
            userId: localStorage.getItem('user_id') || null,
            treks: [],
            staffList: [],
            history: [],
            stats: { total_treks: 0, total_users: 0, total_bookings: 0 },
            newTrek: { name: '', location: '', difficulty: '', duration: '', total_capacity: '', start_date: '', end_date: '' },
            newStaff: { name: '', email: '', password: '' },
            users: [],
            searchQuery: ''
        }
    },
    computed: {
        filteredTreks() {
            if (!this.searchQuery) return this.treks;
            const query = this.searchQuery.toLowerCase();
            return this.treks.filter(t => 
                t.name.toLowerCase().includes(query) || 
                t.location.toLowerCase().includes(query) ||
                t.difficulty.toLowerCase().includes(query)
            );
        }
    },
    mounted() {
        if (this.token) {
            this.fetchTreks();
            if (this.role === 'admin') {
                this.fetchStaffList();
                this.fetchStats();
                this.fetchAllUsers();
            }
            if (this.role === 'trekker') {
                this.fetchHistory();
            }
        }
    },
    methods: {
        async login() {
            const res = await fetch('http://127.0.0.1:5000/api/login', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: this.email, password: this.password })
            });
            const data = await res.json();
            if (res.ok) {
                this.token = data.access_token; this.role = data.role; this.userId = data.user_id;
                localStorage.setItem('access_token', this.token);
                localStorage.setItem('role', this.role);
                localStorage.setItem('user_id', this.userId);
                this.errorMessage = '';
                this.fetchTreks();
                if (this.role === 'admin') {
                    this.fetchStaffList();
                    this.fetchStats();
                    this.fetchAllUsers();
                }
                if (this.role === 'trekker') {
                    this.fetchHistory();
                }
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
                this.isRegistering = false; 
                this.errorMessage = '';
            } else this.errorMessage = data.msg;
        },
        logout() {
            this.token = null; this.role = null; this.userId = null; this.treks = []; this.staffList = []; this.history = [];
            this.users = []; this.searchQuery = '';
            this.stats = { total_treks: 0, total_users: 0, total_bookings: 0 };
            localStorage.clear();
        },
        async fetchTreks() {
            const res = await fetch('http://127.0.0.1:5000/api/treks');
            this.treks = await res.json();
        },
        async fetchStaffList() {
            const res = await fetch('http://127.0.0.1:5000/api/staff_list', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            this.staffList = await res.json();
        },
        async fetchHistory() {
            const res = await fetch('http://127.0.0.1:5000/api/history', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            this.history = await res.json();
        },
        async fetchStats() {
            const res = await fetch('http://127.0.0.1:5000/api/stats', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            this.stats = await res.json();
        },
        async fetchAllUsers() {
            const res = await fetch('http://127.0.0.1:5000/api/users', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            this.users = await res.json();
        },
        async toggleUser(userId) {
            const res = await fetch(`http://127.0.0.1:5000/api/users/${userId}/toggle`, {
                method: 'PUT',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            alert(data.msg);
            this.fetchAllUsers();
            this.fetchStats();
        },
        async deleteTrek(trekId) {
            if (!confirm("Are you sure you want to remove this trek?")) return;
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trekId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            alert(data.msg);
            this.fetchTreks();
            this.fetchStats();
        },
        async createTrek() {
            const res = await fetch('http://127.0.0.1:5000/api/treks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify(this.newTrek)
            });
            if(res.ok) {
                alert("Trek created!");
                this.fetchTreks();
                this.fetchStats();
            } else {
                alert("Failed to create trek.");
            }
        },
        async createStaff() {
            const res = await fetch('http://127.0.0.1:5000/api/staff', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify(this.newStaff)
            });
            const data = await res.json();
            alert(data.msg);
            this.newStaff = { name: '', email: '', password: '' }; 
            this.fetchStaffList();
            this.fetchStats();
            this.fetchAllUsers();
        },
        async assignStaff(trekId, staffId) {
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trekId}/assign`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify({ staff_id: staffId })
            });
            const data = await res.json();
            alert(data.msg);
            this.fetchTreks();
        },
        async updateTrekStatus(trekId, newStatus) {
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trekId}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify({ status: newStatus })
            });
            const data = await res.json();
            alert(data.msg);
            this.fetchTreks();
        },
        async bookTrek(trekId) {
            const res = await fetch(`http://127.0.0.1:5000/api/book/${trekId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            alert(data.msg);
            this.fetchTreks(); 
            this.fetchHistory();
            this.fetchStats();
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