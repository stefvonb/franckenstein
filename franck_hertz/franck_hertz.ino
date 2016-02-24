int v_acc_sensor = 0;
float v_acc = 0.0;
int v_cc_sensor = 0;
float v_cc = 0.0;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  analogReference(DEFAULT);
}

void loop() {
  // put your main code here, to run repeatedly:
  v_acc_sensor = analogRead(A0);
  delay(10);
  v_acc_sensor = analogRead(A0);
  v_acc = v_acc_sensor*(5.0/1023.0);
  v_cc_sensor = analogRead(A1);
  delay(10);
  v_cc_sensor = analogRead(A1);
  v_cc = v_cc_sensor*(5.0/1023.0);
  Serial.print(v_acc);
  Serial.print(",");
  Serial.println(v_cc);
  delay(80);
}
