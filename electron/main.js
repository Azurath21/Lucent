const { app, BrowserWindow, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const Store = require('electron-store');

// Initialize secure store
const store = new Store({
  name: 'lucent-config',
  encryptionKey: 'lucent-carousell-secure-key-2024'
});

let mainWindow;
let serverProcess;

// Hide console errors for better user experience
app.commandLine.appendSwitch('disable-logging');
app.commandLine.appendSwitch('disable-dev-shm-usage');
app.commandLine.appendSwitch('no-sandbox');

function createWindow() {
  // Check for API key - first try environment variable, then stored key
  let apiKey = process.env.GOOGLE_API_KEY || store.get('gemini_api_key');
  
  if (!apiKey) {
    showApiKeySetup();
    return;
  }
  
  // Ensure environment variable is set for the server
  process.env.GOOGLE_API_KEY = apiKey;
  
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'web', 'logo.png'),
    show: false,
    titleBarStyle: 'default'
  });

  // Start the Node.js server
  startServer();

  // Load the app after a short delay to ensure server is running
  setTimeout(() => {
    mainWindow.loadURL('http://127.0.0.1:3000');
  }, 2000);

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startServer() {
  // Import the server directly instead of spawning a separate process
  try {
    // Clear require cache to ensure fresh start
    delete require.cache[require.resolve('./server.js')];
    
    // Require the server module directly
    require('../server.js');
    
    console.log('Server started successfully');
  } catch (error) {
    console.error('Failed to start server:', error.message);
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// API Key Setup Dialog
function showApiKeySetup() {
  const setupWindow = new BrowserWindow({
    width: 500,
    height: 300,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    icon: path.join(__dirname, 'web', 'logo.png'),
    title: 'Lucent Setup - API Key Required'
  });

  setupWindow.loadFile(path.join(__dirname, 'setup.html'));
  
  setupWindow.on('closed', () => {
    if (!store.get('gemini_api_key')) {
      app.quit();
    }
  });
}

// IPC handlers for API key management
ipcMain.handle('save-api-key', async (event, apiKey) => {
  if (!apiKey || apiKey.trim() === '') {
    return { success: false, error: 'API key cannot be empty' };
  }
  
  try {
    store.set('gemini_api_key', apiKey.trim());
    process.env.GOOGLE_API_KEY = apiKey.trim();
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('get-api-key', async () => {
  return store.get('gemini_api_key', '');
});

ipcMain.handle('clear-api-key', async () => {
  store.delete('gemini_api_key');
  delete process.env.GOOGLE_API_KEY;
  return { success: true };
});

ipcMain.handle('restart-app', async () => {
  app.relaunch();
  app.exit();
});

// Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    shell.openExternal(navigationUrl);
  });
});
