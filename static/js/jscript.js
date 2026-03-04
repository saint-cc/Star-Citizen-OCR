// Function to generate a unique ID
function generateId() {
    return Math.random().toString(36).substr(2, 9);
}

// Function to add a new key mapping
function addKeyMapping() {
    document.getElementById('key-mapping-form').classList.remove('hidden');
    document.getElementById('key-mapping-form-title').textContent = 'Add Key Mapping';
    document.getElementById('key-mapping-edit-form').reset();
	document.getElementById('key-mapping-id').value = ''; // Clear the hidden input fields
}

// Function to encrypt data
function encryptData(data, password) {
    // Simple encryption logic (for demonstration purposes)
    // In a real application, use a proper encryption library
    const encryptedData = btoa(JSON.stringify(data) + password);
    return encryptedData;
}

// Function to decrypt data
function decryptData(encryptedData, password) {
    // Simple decryption logic (for demonstration purposes)
    // In a real application, use a proper decryption library
    const decryptedData = atob(encryptedData).slice(0, -password.length);
    return JSON.parse(decryptedData);
}

// Function to check if user data exists in local storage
function userDataExists(username) {
    return localStorage.getItem(username) !== null;
}

// Function to save user data to local storage
function saveUserData(username, password, data) {
    const encryptedData = encryptData(data, password);
    localStorage.setItem(username, encryptedData);
}

// Function to load user data from local storage
function loadUserData(username, password) {
    const encryptedData = localStorage.getItem(username);
    let userData;
    if (!encryptedData) {
        // No user yet, create default structure
        userData = {
            keyMappings: [],
            macros: [],
            dashboards: []
        };
    } else {
        try {
            userData = decryptData(encryptedData, password);
        } catch (e) {
            console.error("Failed to decrypt user data:", e);
            return null;
        }
    }

    // --- Add default key mappings if empty ---
    if (!userData.keyMappings || userData.keyMappings.length === 0) {
        userData.keyMappings = [
            { id: "1", key: { key: 'w', duration: 0, modifiers: '' }, name: 'forward' },
            { id: "2", key: { key: 's', duration: 0, modifiers: '' }, name: 'back' },
            { id: "3", key: { key: 'a', duration: 0, modifiers: '' }, name: 'left' },
            { id: "4", key: { key: 'd', duration: 0, modifiers: '' }, name: 'right' },
            { id: "5", key: { key: 'q', duration: 0, modifiers: '' }, name: 'roll_L' },
            { id: "6", key: { key: 'e', duration: 0, modifiers: '' }, name: 'roll_R' },
            { id: "7", key: { key: ' ', duration: 1, modifiers: '' }, name: 'up' },
            { id: "8", key: { key: 'ctrl', duration: 0, modifiers: '' }, name: 'down' },
            { id: "9", key: { key: 'u', duration: 0, modifiers: '' }, name: 'system' },
            { id: "10", key: { key: 'i', duration: 0, modifiers: '' }, name: 'engine' },
            { id: "11", key: { key: 'b', duration: 1, modifiers: '' }, name: 'mode' },
            { id: "12", key: { key: 'n', duration: 0, modifiers: '' }, name: 'gear' }
        ];
    }

    return userData;
}


// Function to handle user login (extended with global variables for username and password)
let currentUsername = null;
let currentPassword = null;

function handleLogin(event) {
    event.preventDefault();
    currentUsername = document.getElementById('username').value;
    currentPassword = document.getElementById('password').value;

    if (userDataExists(currentUsername)) {
        const userData = loadUserData(currentUsername, currentPassword);
        if (userData) {
            // User data exists and is loaded successfully
            console.log('User data loaded:', userData);
            // Proceed with loading the application
            document.getElementById('login-container').classList.add('hidden');
            document.getElementById('app-container').classList.remove('hidden');
            loadKeyMappings();
            loadMacros();
			loadDashboard();
        } else {
            // Password is incorrect
            alert('Incorrect password. Please try again.');
        }
    } else {
        // No user data exists, ask if the user wants to create a new account
        const createNewAccount = confirm('No account found. Would you like to create a new account?');
        if (createNewAccount) {
            const initialData = {
                keyMappings: [],
                macros: [],
				dashboard: []
            };
            saveUserData(currentUsername, currentPassword, initialData);
            alert('Account created successfully. Please log in again.');
        }
    }
}

function generate_orderId() {
    // Load the current user data
    let userData = loadUserData(currentUsername, currentPassword);

    // Check if there are any key mappings
    if (userData.keyMappings.length === 0) {
        return 1; // If there are no key mappings, start with 1
    }

    // Find the maximum orderIndex in the existing key mappings
    const maxOrderIndex = Math.max(...userData.keyMappings.map(mapping => mapping.orderIndex || 0));

    // Return the next orderIndex
    return maxOrderIndex + 1;
}

function saveKeyMapping(event) {
    event.preventDefault();
    const id = document.getElementById('key-mapping-id').value || generateId();
    const name = document.getElementById('key-name').value;
    const key = document.getElementById('key').value;
    const duration = parseInt(document.getElementById('duration').value) || 0;
    const modifiers = document.getElementById('modifiers').value.split(',').map(mod => mod.trim());

    // Generate or use existing orderIndex
    const orderIndex = document.getElementById('orderindex').value || generate_orderId();

    const keyMapping = {
        id: id,
        name: name,
        key: {
            key: key,
            duration: duration,
            modifiers: modifiers
        },
        orderIndex: orderIndex
    };

    let userData = loadUserData(currentUsername, currentPassword);
    const existingIndex = userData.keyMappings.findIndex(mapping => mapping.id === id);

    if (existingIndex >= 0) {
        userData.keyMappings[existingIndex] = keyMapping;
    } else {
        userData.keyMappings.push(keyMapping);
    }

    saveUserData(currentUsername, currentPassword, userData);
    loadKeyMappings();
    document.getElementById('key-mapping-form').classList.add('hidden');
}


// Function to edit an existing key mapping
function editKeyMapping(id) {
		let userData = loadUserData(currentUsername, currentPassword) || {
		keyMappings: [],
		macros: [],
		dashboard: []
	};
    const keyMapping = userData.keyMappings.find(mapping => mapping.id === id);

    if (keyMapping) {
        document.getElementById('key-mapping-id').value = keyMapping.id;
        document.getElementById('key-name').value = keyMapping.name;
        document.getElementById('key').value = keyMapping.key.key;
        document.getElementById('duration').value = keyMapping.key.duration;
        document.getElementById('modifiers').value = keyMapping.key.modifiers.join(', ');

        // Set the order index in the hidden field
        document.getElementById('orderindex').value = keyMapping.orderIndex;

        document.getElementById('key-mapping-form').classList.remove('hidden');
        document.getElementById('key-mapping-form-title').textContent = 'Edit Key Mapping';
    }
}

// Function to delete a key mapping
function deleteKeyMapping(id) {
    let userData = loadUserData(currentUsername, currentPassword);
    userData.keyMappings = userData.keyMappings.filter(mapping => mapping.id !== id);

    // Remove corresponding macros that use this key mapping
    userData.macros = userData.macros.map(macro => ({
        ...macro,
        keylist: macro.keylist.filter(keyId => keyId !== id)
    }));

    saveUserData(currentUsername, currentPassword, userData);
    loadKeyMappings();
    loadMacros();
}

function moveItem(id, direction) {
    let userData = loadUserData(currentUsername, currentPassword);
    const index = userData.keyMappings.findIndex(mapping => mapping.id === id);
    if (index > -1) {
        if (direction === 'up' && index > 0) {
            swap(userData.keyMappings, index, index - 1);
        } else if (direction === 'down' && index < userData.keyMappings.length - 1) {
            swap(userData.keyMappings, index, index + 1);
        }
        saveUserData(currentUsername, currentPassword, userData);
        loadKeyMappings(); // Refresh UI
    }
}

function swap(arr, i, j) {
    [arr[i], arr[j]] = [arr[j], arr[i]];
}

// Function to load key mapping
function loadKeyMappings() {
    let userData = loadUserData(currentUsername, currentPassword);
    const keyMappingsList = document.getElementById('key-mappings-list');
    keyMappingsList.innerHTML = '';

    userData.keyMappings.forEach(mapping => {
        const listItem = document.createElement('li');
        listItem.textContent = `${mapping.name} (${mapping.key.key})`;

        // Create a container for the buttons
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'button-container'; // Add a class for styling

        // Create and configure the edit button
        const editButton = document.createElement('button');
        editButton.textContent = 'Edit';
        editButton.onclick = () => editKeyMapping(mapping.id);

        // Create and configure the delete button
        const deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.onclick = () => deleteKeyMapping(mapping.id);

        // Create and configure the send button
        const sendButton = document.createElement('button');
        sendButton.textContent = 'Send';
        sendButton.onclick = () => sendKey(mapping.id);

		// Create and configure the up button
		const upButton = document.createElement('button');
		upButton.innerHTML = '&#x25B2;';
		upButton.onclick = () => moveItem(mapping.id, 'up');  // Pass the correct id

		// Create and configure the down button
		const downButton = document.createElement('button');
		downButton.innerHTML = '&#x25BC;';
		downButton.onclick = () => moveItem(mapping.id, 'down');  // Pass the correct id

		buttonContainer.appendChild(upButton);
		buttonContainer.appendChild(downButton);

        // Append buttons to the container
        buttonContainer.appendChild(editButton);
        buttonContainer.appendChild(deleteButton);
        buttonContainer.appendChild(sendButton);

        // Append the button container to the list item
        listItem.appendChild(buttonContainer);

        // Append the list item to the list
        keyMappingsList.appendChild(listItem);
    });
}

// Function to add a new macro
function addMacro() {
    document.getElementById('macro-id').value = '';
    document.getElementById('macro-name').value = '';
    document.getElementById('selected-keys').innerHTML = '';
    document.getElementById('macro-form').classList.remove('hidden');
    document.getElementById('macro-form-title').textContent = 'Add Macro';
    populateKeySelect();
}


// Function to populate the select element with key mappings from userData
function populateKeySelect() {
    const selectElement = document.getElementById('macro-keys-select');
    selectElement.innerHTML = ''; // Clear existing options

    // Load user data to get the key mappings
    let userData = loadUserData(currentUsername, currentPassword);

    userData.keyMappings.forEach(mapping => {
        const option = document.createElement('option');
        option.value = mapping.id; // Use the id as the value
        option.textContent = mapping.name; // Display name
        selectElement.appendChild(option);
    });
}

// Function to add a key to the list of selected keys
function addKey() {
    const selectElement = document.getElementById('macro-keys-select');
    const selectedKeyId = selectElement.value;
    const keyContainer = document.getElementById('selected-keys');

    // Load user data to get the selected key mapping
    let userData = loadUserData(currentUsername, currentPassword);
    const selectedKeyMapping = userData.keyMappings.find(mapping => mapping.id === selectedKeyId);

    // Create a span element to display the selected key
    const keySpan = document.createElement('span');
    keySpan.textContent = selectedKeyMapping.name;
    keySpan.classList.add('selected-key');
    keySpan.dataset.keyId = selectedKeyId;

    // Add a remove button to the key span
    const removeButton = document.createElement('button');
    removeButton.textContent = 'Remove';
    removeButton.type = 'button';
    removeButton.onclick = () => {
        keyContainer.removeChild(keySpan);
    };
    keySpan.appendChild(removeButton);

    // Append the key span to the container
    keyContainer.appendChild(keySpan);
}

// Modify the saveMacro function to include the selected keys
function saveMacro(event) {
    event.preventDefault();
    const id = document.getElementById('macro-id').value || generateId();
    const name = document.getElementById('macro-name').value;

    // Get the list of selected keys
    const keyContainer = document.getElementById('selected-keys');
    const keylist = Array.from(keyContainer.getElementsByClassName('selected-key')).map(span => span.dataset.keyId);

    const macro = {
        id: id,
        name: name,
        keylist: keylist
    };

    let userData = loadUserData(currentUsername, currentPassword);
    const existingIndex = userData.macros.findIndex(macro => macro.id === id);

    if (existingIndex >= 0) {
        userData.macros[existingIndex] = macro;
    } else {
        userData.macros.push(macro);
    }

    saveUserData(currentUsername, currentPassword, userData);
    loadMacros();
    document.getElementById('macro-form').classList.add('hidden');
}

// Function to edit an existing macro
function editMacro(id) {
    let userData = loadUserData(currentUsername, currentPassword);
    const macro = userData.macros.find(macro => macro.id === id);

    if (macro) {
        document.getElementById('macro-id').value = macro.id;
        document.getElementById('macro-name').value = macro.name;

        // Clear existing selected keys
        const keyContainer = document.getElementById('selected-keys');
        keyContainer.innerHTML = '';

        // Add the keys from the macro to the selected keys list
        macro.keylist.forEach(keyId => {
            const keyMapping = userData.keyMappings.find(mapping => mapping.id === keyId);

            const keySpan = document.createElement('span');
            keySpan.textContent = keyMapping.name;
            keySpan.classList.add('selected-key');
            keySpan.dataset.keyId = keyId;

            const removeButton = document.createElement('button');
            removeButton.textContent = 'X';
            removeButton.type = 'button';
            removeButton.onclick = () => {
                keyContainer.removeChild(keySpan);
            };
            keySpan.appendChild(removeButton);

            keyContainer.appendChild(keySpan);
        });

        document.getElementById('macro-form').classList.remove('hidden');
        document.getElementById('macro-form-title').textContent = 'Edit Macro';
		populateKeySelect(); // Call it here to ensure the select is populated
    }
}

// Function to delete a macro
function deleteMacro(id) {
    let userData = loadUserData(currentUsername, currentPassword);
    userData.macros = userData.macros.filter(macro => macro.id !== id);

    saveUserData(currentUsername, currentPassword, userData);
    loadMacros();
}

// Function to load macros
function loadMacros() {
    let userData = loadUserData(currentUsername, currentPassword);
    const macrosList = document.getElementById('macros-list');
    macrosList.innerHTML = '';

    userData.macros.forEach(macro => {
        const listItem = document.createElement('li');
        listItem.textContent = `${macro.name}`;

        // Create a container for the buttons
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'button-container'; // Add a class for styling

        // Create and configure the edit button
        const editButton = document.createElement('button');
        editButton.textContent = 'Edit';
        editButton.onclick = () => editMacro(macro.id);

        // Create and configure the delete button
        const deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.onclick = () => deleteMacro(macro.id);

        // Create and configure the send button
        const sendButton = document.createElement('button');
        sendButton.textContent = 'Send';
        sendButton.onclick = () => sendMacro(macro.id);

        // Append buttons to the container
        buttonContainer.appendChild(editButton);
        buttonContainer.appendChild(deleteButton);
        buttonContainer.appendChild(sendButton);

        // Append the button container to the list item
        listItem.appendChild(buttonContainer);

        // Append the list item to the list
        macrosList.appendChild(listItem);
    });
}

// Function to send a key mapping as a macro
function sendKey(id) {
    let userData = loadUserData(currentUsername, currentPassword);
    let keyMapping = userData.keyMappings.find(km => km.id === id);
    if (keyMapping) {
        // Extract the relevant properties from keyMapping
        let macro = {
            keylist: [{
                key: keyMapping.key.key,  // Assuming keyMapping.key is an object with the 'key' property
                duration: keyMapping.key.duration,
                modifiers: keyMapping.key.modifiers
            }]
        };
        
        console.log('macro:', JSON.stringify(macro));
        
        fetch('/play_macro', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(macro)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // alert('Key sent successfully.');
            } else {
                alert('Error sending key.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    }
}

// Function to send a macro
function sendMacro(id) {
    let userData = loadUserData(currentUsername, currentPassword);
    let macro = userData.macros.find(m => m.id === id);

    if (macro) {
        // Create a list to hold the key mappings with only the relevant properties
        let keyMappingsList = [];

        // Log the macro data and key mappings
        console.log('Macro data:', macro);
        console.log('Key mappings:', userData.keyMappings);

        // Iterate over the unique IDs in the macro's keylist
        macro.keylist.forEach(keyId => {
            // Find the key mapping using the unique ID
            let keyMapping = userData.keyMappings.find(mapping => mapping.id === keyId);

            // Log the result of the search
            console.log('Searching key mapping with id:', keyId);
            console.log('Found key mapping:', keyMapping);

            if (keyMapping) {
                // Add the relevant properties to the list
                keyMappingsList.push({
                    key: keyMapping.key.key,  // Assuming keyMapping.key is an object with the 'key' property
                    duration: keyMapping.key.duration,
                    modifiers: keyMapping.key.modifiers
                });
            } else {
                console.warn('No key mapping found with id', keyId);
            }
        });

        // Prepare the macro data to send
        let macroData = { keylist: keyMappingsList };

        // Log the final payload for debugging
        console.log('sendMacro payload:', JSON.stringify(macroData));

        fetch('/play_macro', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(macroData)
        })
		.then(response => {
			console.log('Response status:', response.status);
			return response.json();
		})
		.then(data => {
			console.log('Response data:', data);
			if (data.status === 'success') {
				console.log('Macro sent successfully.');
			} else {
				alert('Error sending macro.');
			}
		})
        .catch(error => {
            console.error('Error:', error);
        });
    } else {
        console.warn('No macro found with id', id);
    }
}

// Function to submit the list of keys to the server
function submitKeys() {
    let userData = loadUserData(currentUsername, currentPassword);
    fetch('/submit_keys', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ keys: userData.keyMappings })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // alert('Keys submitted successfully.');
        } else {
            alert('Error submitting keys.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// --- DASHBOARD FUNCTIONS ---
function generateButtonId() {
    return Math.random().toString(36).substr(2, 9);
}

function loadDashboard() {
    const userData = loadUserData(currentUsername, currentPassword);
    const list = document.getElementById('dashboards-list');
    list.innerHTML = '';

    if (!userData || !Array.isArray(userData.dashboards)) {
        console.warn('No dashboards found for user:', currentUsername);
        return; // nothing to list
    }

    userData.dashboards.forEach(dashboard => {
        const li = document.createElement('li');
        li.textContent = dashboard.name;

        const editBtn = document.createElement('button');
        editBtn.textContent = 'Edit';
        editBtn.onclick = () => editDashboard(dashboard.id);

        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.onclick = () => deleteDashboard(dashboard.id);

        li.appendChild(editBtn);
        li.appendChild(deleteBtn);

        list.appendChild(li);
    });
}


function addDashboard() {
    document.getElementById('dashboard-edit-form').reset();
    document.getElementById('dashboard-id').value = '';
    document.getElementById('dashboard-buttons-list').innerHTML = '';
    document.getElementById('dashboard-form-title').textContent = 'Add Dashboard';
    populateMacroSelect('new-button-macro');
    document.getElementById('dashboard-form').classList.remove('hidden');
}

function editDashboard(dashboardId) {
    let userData = loadUserData(currentUsername, currentPassword);
    const dashboard = userData.dashboards.find(d => d.id === dashboardId);
    if (!dashboard) return;

    document.getElementById('dashboard-id').value = dashboard.id;
    document.getElementById('dashboard-name').value = dashboard.name;
    document.getElementById('dashboard-buttons-list').innerHTML = '';

    populateMacroSelect('new-button-macro');

    dashboard.buttons.forEach(btn => addDashboardButtonToList(btn));

    document.getElementById('dashboard-form-title').textContent = 'Edit Dashboard';
    document.getElementById('dashboard-form').classList.remove('hidden');
}

function populateMacroSelect(selectId) {
    const select = document.getElementById(selectId);
    select.innerHTML = '';
    let userData = loadUserData(currentUsername, currentPassword);
    userData.macros.forEach(macro => {
        const option = document.createElement('option');
        option.value = macro.id;
        option.textContent = macro.name;
        select.appendChild(option);
    });
}

function addDashboardButtonToList(button) {
    const list = document.getElementById('dashboard-buttons-list');
    const li = document.createElement('li');
    li.textContent = `${button.name} -> ${getMacroName(button.macroId)}`;

    const removeBtn = document.createElement('button');
    removeBtn.textContent = 'Remove';
    removeBtn.type = 'button';
    removeBtn.onclick = () => list.removeChild(li);

    li.appendChild(removeBtn);
    li.dataset.buttonId = button.id;
    li.dataset.macroId = button.macroId;
    li.dataset.buttonName = button.name;

    list.appendChild(li);
}

function getMacroName(macroId) {
    let userData = loadUserData(currentUsername, currentPassword);
    const macro = userData.macros.find(m => m.id === macroId);
    return macro ? macro.name : 'Unknown Macro';
}

document.getElementById('add-dashboard-button').addEventListener('click', () => {
    const name = document.getElementById('new-button-name').value.trim();
    const macroId = document.getElementById('new-button-macro').value;
    if (!name || !macroId) return;

    const button = { id: generateButtonId(), name, macroId };
    addDashboardButtonToList(button);
    document.getElementById('new-button-name').value = '';
});

function saveDashboard(event) {
    event.preventDefault();

    const id = document.getElementById('dashboard-id').value || generateId();
    const name = document.getElementById('dashboard-name').value;

    const buttons = Array.from(document.getElementById('dashboard-buttons-list').children).map(li => ({
        id: li.dataset.buttonId,
        name: li.dataset.buttonName,
        macroId: li.dataset.macroId
    }));

    let userData = loadUserData(currentUsername, currentPassword);

    // ensure userData and dashboards exist
    if (!userData) userData = {};
    if (!Array.isArray(userData.dashboards)) userData.dashboards = [];

    const existingIndex = userData.dashboards.findIndex(d => d.id === id);

    const dashboard = { id, name, buttons };

    if (existingIndex >= 0) {
        userData.dashboards[existingIndex] = dashboard;
    } else {
        userData.dashboards.push(dashboard);
    }

    saveUserData(currentUsername, currentPassword, userData);
    loadDashboard();
    document.getElementById('dashboard-form').classList.add('hidden');
}


function deleteDashboard(id) {
    let userData = loadUserData(currentUsername, currentPassword);
    userData.dashboards = userData.dashboards.filter(d => d.id !== id);
    saveUserData(currentUsername, currentPassword, userData);
    loadDashboard();
}


// Initial setup
function init() {
	document.getElementById('add-key').addEventListener('click', addKey);

	// Populate key select when the form is opened
	document.getElementById('macro-form').addEventListener('classlistchange', populateKeySelect);

    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('add-key-mapping').addEventListener('click', addKeyMapping);
    document.getElementById('key-mapping-edit-form').addEventListener('submit', saveKeyMapping);
    document.getElementById('cancel-key-mapping').addEventListener('click', () => {
        document.getElementById('key-mapping-form').classList.add('hidden');
    });
    document.getElementById('add-macro').addEventListener('click', addMacro);
    document.getElementById('macro-edit-form').addEventListener('submit', saveMacro);
    document.getElementById('cancel-macro').addEventListener('click', () => {
        document.getElementById('macro-form').classList.add('hidden');
    });
	
	document.getElementById('add-dashboard').addEventListener('click', addDashboard);
document.getElementById('dashboard-edit-form').addEventListener('submit', saveDashboard);
document.getElementById('cancel-dashboard').addEventListener('click', () => {
    document.getElementById('dashboard-form').classList.add('hidden');
});
}

document.addEventListener('DOMContentLoaded', init);
