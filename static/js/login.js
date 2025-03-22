document.addEventListener('DOMContentLoaded', function() {
    // 密码显示/隐藏切换
    const togglePassword = document.querySelector('.toggle-password');
    const passwordField = document.querySelector('#id_password');

    if (togglePassword && passwordField) {
        togglePassword.addEventListener('click', function() {
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);

            // 切换图标
            const eyeIcon = this.querySelector('i');
            eyeIcon.classList.toggle('bi-eye');
            eyeIcon.classList.toggle('bi-eye-slash');
        });
    }
}); 