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
            stats: { total_treks: 0, total_users: 0, total_staff: 0, total_bookings: 0 },
            newTrek: { name: '', location: '', difficulty: '', duration: '', total_capacity: '', start_date: '', end_date: '' },
            newStaff: { name: '', email: '', password: '' },
            users: [],
            searchQuery: '',
            profile: { name: '', phone: '', city: '' },
            participants: [],
            allBookings: [],
            filterDifficulty: '',
            filterDuration: '',
            searchUserQuery: '',
            exportStatus: null,
            exportFileUrl: null,
            publicStats: { active_treks: 0, happy_trekkers: 0 },
            currentView: ''
        }
    },
    computed: {
        filteredTreks() {
            let result = this.treks;
            
            // Trekkers should only see Open and Approved treks
            if (this.role === 'trekker') {
                result = result.filter(t => t.status === 'Open' || t.status === 'Approved');
            }
            
            // Search filter
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                result = result.filter(t => 
                    t.name.toLowerCase().includes(query) || 
                    t.location.toLowerCase().includes(query) ||
                    t.difficulty.toLowerCase().includes(query)
                );
            }
            
            // Dropdown difficulty filter
            if (this.filterDifficulty) {
                result = result.filter(t => t.difficulty === this.filterDifficulty);
            }
            
            // Duration filter
            if (this.filterDuration) {
                result = result.filter(t => t.duration <= this.filterDuration);
            }
            
            return result;
        },
        filteredUsers() {
            if (!this.searchUserQuery) return this.users;
            const query = this.searchUserQuery.toLowerCase();
            return this.users.filter(u => 
                u.name.toLowerCase().includes(query) || 
                u.email.toLowerCase().includes(query)
            );
        }
    },
    mounted() {
        fetch('http://127.0.0.1:5000/api/public_stats')
            .then(res => res.json())
            .then(data => this.publicStats = data);
        if (this.token) {
            this.currentView = this.role === 'admin' ? 'dashboard' : (this.role === 'staff' ? 'treks' : 'explore');
            this.fetchTreks();
            if (this.role === 'admin') {
                this.fetchStaffList();
                this.fetchStats();
                this.fetchAllUsers();
                this.fetchAllBookings();
            }
            if (this.role === 'trekker') {
                this.fetchHistory();
                this.fetchProfile();
            }
            if (this.role === 'staff') {
                this.fetchProfile();
            }
        }
    },
    methods: {
        setView(view) {
            this.currentView = view;
            this.errorMessage = '';
            this.successMessage = '';
            if (view === 'dashboard' && this.role === 'admin') {
                this.$nextTick(() => {
                    this.fetchStats();
                });
            }
        },
        async login() {
            const res = await fetch('http://127.0.0.1:5000/api/login', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: this.email, password: this.password })
            });
            const data = await res.json();
            if (res.ok) {
                this.token = data.access_token; this.role = data.role; this.userId = data.user_id;
                this.currentView = this.role === 'admin' ? 'dashboard' : (this.role === 'staff' ? 'treks' : 'explore');
                localStorage.setItem('access_token', this.token);
                localStorage.setItem('role', this.role);
                localStorage.setItem('user_id', this.userId);
                this.errorMessage = '';
                this.successMessage = 'Logged in successfully!';
                this.fetchTreks();
                if (this.role === 'admin') {
                    this.fetchStaffList();
                    this.fetchStats();
                    this.fetchAllUsers();
                    this.fetchAllBookings();
                }
                if (this.role === 'trekker') {
                    this.fetchHistory();
                    this.fetchProfile();
                }
                if (this.role === 'staff') {
                    this.fetchProfile();
                }
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
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
            this.currentView = '';
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
            
            // Draw Chart
            if (this.role === 'admin') {
                setTimeout(() => {
                    const ctx = document.getElementById('adminChart');
                    if (ctx) {
                        if (window.myChart) window.myChart.destroy();
                        window.myChart = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: ['Treks', 'Trekkers', 'Staff', 'Bookings'],
                                datasets: [{
                                    label: 'System Totals',
                                    data: [this.stats.total_treks, this.stats.total_users, this.stats.total_staff, this.stats.total_bookings],
                                    backgroundColor: ['#2b5329', '#ff6b35', '#17a2b8', '#ffc107']
                                }]
                            }
                        });
                    }
                }, 100);
            }
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
            if (res.ok) {
                this.successMessage = data.msg;
                this.errorMessage = '';
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
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
            if (res.ok) {
                this.successMessage = data.msg;
                this.errorMessage = '';
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
            this.fetchTreks();
            this.fetchStats();
        },
        async createTrek() {
            const res = await fetch('http://127.0.0.1:5000/api/treks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify(this.newTrek)
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = "Trek created successfully!";
                this.errorMessage = '';
                this.newTrek = { name: '', location: '', difficulty: '', duration: '', total_capacity: '', start_date: '', end_date: '' };
                this.fetchTreks();
                this.fetchStats();
            } else {
                this.errorMessage = data.msg || "Failed to create trek.";
                this.successMessage = '';
            }
        },
        async createStaff() {
            const res = await fetch('http://127.0.0.1:5000/api/staff', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify(this.newStaff)
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = data.msg;
                this.errorMessage = '';
                this.newStaff = { name: '', email: '', password: '' }; 
                this.fetchStaffList();
                this.fetchStats();
                this.fetchAllUsers();
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
        },
        async assignStaff(trekId, staffId) {
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trekId}/assign`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify({ staff_id: staffId })
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = data.msg;
                this.errorMessage = '';
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
            this.fetchTreks();
        },
        async updateTrekStatus(trekId, newStatus) {
            // Deprecated status update, using manageTrekSlots now, but keeping for compatibility
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trekId}/manage`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify({ status: newStatus })
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = data.msg;
                this.errorMessage = '';
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
            this.fetchTreks();
        },
        async bookTrek(trekId) {
            const res = await fetch(`http://127.0.0.1:5000/api/book/${trekId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = data.msg;
                this.errorMessage = '';
                this.fetchTreks(); 
                this.fetchHistory();
                this.fetchStats();
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
        },
        async exportHistory() {
            this.exportStatus = 'Initiating export...';
            this.exportFileUrl = null;
            const res = await fetch('http://127.0.0.1:5000/api/export', {
                method: 'POST', headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            if (res.ok) {
                this.pollExport(data.task_id);
            } else {
                this.errorMessage = data.msg;
                this.exportStatus = 'Failed';
            }
        },
        async pollExport(taskId) {
            this.exportStatus = 'Processing...';
            const interval = setInterval(async () => {
                const res = await fetch(`http://127.0.0.1:5000/api/export/status/${taskId}`, {
                    headers: { 'Authorization': `Bearer ${this.token}` }
                });
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    clearInterval(interval);
                    this.exportStatus = 'Complete!';
                    this.exportFileUrl = `http://127.0.0.1:5000/api/download/${data.file}`;
                } else if (data.status === 'FAILURE' || data.status === 'REVOKED') {
                    clearInterval(interval);
                    this.exportStatus = 'Export failed or cancelled.';
                }
            }, 2000);
        },
        async fetchProfile() {
            const res = await fetch('http://127.0.0.1:5000/api/profile', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (res.ok) {
                this.profile = await res.json();
            }
        },
        async updateProfile() {
            const res = await fetch('http://127.0.0.1:5000/api/profile', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify(this.profile)
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = "Profile updated successfully!";
                this.errorMessage = '';
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
        },
        async manageTrekSlots(trek) {
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trek.id}/manage`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.token}` },
                body: JSON.stringify({ available_slots: trek.available_slots, status: trek.status })
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = "Trek slots/status updated successfully!";
                this.errorMessage = '';
                this.fetchTreks();
            } else {
                this.errorMessage = data.msg;
                this.successMessage = '';
            }
        },
        async fetchParticipants(trekId) {
            const res = await fetch(`http://127.0.0.1:5000/api/treks/${trekId}/participants`, {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (res.ok) {
                this.participants = await res.json();
                // Scroll to participants list for better UX
                setTimeout(() => {
                    document.getElementById('participants-section')?.scrollIntoView({ behavior: 'smooth' });
                }, 100);
            }
        },
        async fetchAllBookings() {
            const res = await fetch('http://127.0.0.1:5000/api/all_bookings', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (res.ok) {
                this.allBookings = await res.json();
            }
        },
        async cancelBooking(bookingId) {
            if (!confirm("Are you sure you want to cancel this booking?")) return;
            const res = await fetch(`http://127.0.0.1:5000/api/bookings/${bookingId}/cancel`, {
                method: 'PUT',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            const data = await res.json();
            if (res.ok) {
                this.successMessage = data.msg;
                this.fetchHistory();
                this.fetchTreks();
            } else {
                this.errorMessage = data.msg;
            }
        }
    }
}).mount('#app');