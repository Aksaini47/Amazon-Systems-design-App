(() => {
  const el=document.querySelector('#ap_email') || document.querySelector('input[name=email]') || document.querySelector('input[type=email]') || document.querySelector('input[type=text]');
  if(!el) return {ok:false, reason:'no input'};
  const proto=Object.getPrototypeOf(el);
  const desc=Object.getOwnPropertyDescriptor(proto,'value')||Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');
  if(desc&&desc.set) desc.set.call(el, "arunsaini416@gmail.com");
  else el.value="arunsaini416@gmail.com";
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  const f=document.querySelector('form');
  if(f) f.requestSubmit();
  return {ok:true, len: el.value.length};
})()