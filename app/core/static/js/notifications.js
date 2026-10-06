document.addEventListener('alpine:init', () => {
    Alpine.data('notificationMenu', () => ({
        notifications: [],
        loading: false,
        hasMore: false,

        get unreadCount() {
            return this.notifications.length;
        },

        async fetchNotifications() {
            this.loading = true;
            try {
                // Fetch the first 15 unread notifications regardless of age.
                const response = await fetch('/api/v1/notifications?include_read=false&recent_only=false');
                if (!response.ok) throw new Error('Network response was not ok');

                const data = await response.json();

                this.notifications = data.notifications || data || [];
                this.hasMore = Boolean(data.has_more);
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
                await this.fetchNotifications();
            } catch (error) {
                console.error(error);
                // Revert the UI array if the backend request fails
                this.notifications = previousState;
            }
        },

        formatDate(isoString) {
            return window.formatDateTime(isoString);
        }
    }));
});
