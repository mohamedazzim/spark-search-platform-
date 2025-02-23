document.getElementById('login-form').addEventListener('submit', function(e) {
  e.preventDefault(); // Prevent default form submission

  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value.trim();
  const loginMessage = document.getElementById('login-message');

  // Hard-coded credentials: Admin / Admin@123
  if (username === 'Admin' && password === 'Admin@123') {
    loginMessage.textContent = 'Login successful!';
    loginMessage.style.color = 'green';

    // Delay the redirect to let the user see the success message
    setTimeout(() => {
      window.location.href = '/dashboard';
    }, 1000);
  } else {
    loginMessage.textContent = 'Invalid username or password.';
    loginMessage.style.color = 'red';
  }
});
