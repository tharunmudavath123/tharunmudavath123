function toggleMenu(){
  document.getElementById('navLinks').classList.toggle('show');
}
document.querySelectorAll('#navLinks a').forEach(a=>{
  a.addEventListener('click',()=>document.getElementById('navLinks').classList.remove('show'));
});
document.getElementById('year').textContent = new Date().getFullYear();

function sendWhatsApp(event){
  event.preventDefault();
  const name = document.getElementById('name').value;
  const pickup = document.getElementById('pickup').value;
  const destination = document.getElementById('destination').value;
  const date = document.getElementById('date').value;
  const vehicle = document.getElementById('vehicle').value;
  const message = `Hi Gayathri Tours & Travels,
I want to book a taxi.

Name: ${name}
Pickup: ${pickup}
Destination: ${destination}
Date: ${date}
Vehicle: ${vehicle}`;
  const phone = '919652211193';
  window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, '_blank');
}