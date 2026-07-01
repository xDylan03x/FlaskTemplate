document.addEventListener('alpine:init', () => {
    Alpine.data('notificationMenu', () => ({
        notifications: [],
        loading: false,

        get unreadCount() {
            return this.notifications.length;
        },

        async fetchNotifications() {
            this.loading = true;
            try {
                // Fetching default list (last 7 days, unread only)
                const response = await fetch('/api/v1/notifications?include_read=false');
                if (!response.ok) throw new Error('Network response was not ok');

                const data = await response.json();

                // Adjust this line depending on your Flask JSON structure
                // (e.g., if you return { "notifications": [...] } or just the array)
                this.notifications = data.notifications || data || [];
            } catch (error) {
                console.error('Failed to fetch notifications:', error);
            } finally {
                this.loading = false;
            }
        },

        async markAsRead(id) {
            // Optimistic UI Update: Remove it immediately for a snappy feel
            const previousState = [...this.notifications];
            this.notifications = this.notifications.filter(n => n.id !== id);

            try {
                const response = await fetch(`/api/v1/notifications/${id}`, {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        // 'X-CSRFToken': getCookie('csrf_token') // Uncomment if Flask-WTF CSRF is enabled
                    },
                    body: JSON.stringify({read: true})
                });

                if (!response.ok) {
                    throw new Error('Failed to update notification status on server');
                }
            } catch (error) {
                console.error(error);
                // Revert the UI array if the backend request fails
                this.notifications = previousState;
            }
        },

        formatDate(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            return date.toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit'
            });
        }
    }));
});
