document.addEventListener('DOMContentLoaded', function() {
    const userTypeSelect = document.getElementById('id_user_type');
    const teacherFields = document.querySelectorAll('.teacher-field');
    const studentFields = document.querySelectorAll('.student-field');
    
    function toggleFields() {
        const selectedValue = userTypeSelect.value;
        
        if (selectedValue === 'teacher') {
            teacherFields.forEach(field => {
                field.style.display = 'block';
                field.classList.add('animate-in');
            });
            studentFields.forEach(field => field.style.display = 'none');
        } else if (selectedValue === 'student') {
            teacherFields.forEach(field => field.style.display = 'none');
            studentFields.forEach(field => {
                field.style.display = 'block';
                field.classList.add('animate-in');
            });
        } else {
            teacherFields.forEach(field => field.style.display = 'none');
            studentFields.forEach(field => field.style.display = 'none');
        }
    }
    
    // 初始化
    toggleFields();
    
    // 监听变化
    userTypeSelect.addEventListener('change', toggleFields);
}); 