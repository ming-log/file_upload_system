# Student Optional Email and Excel Import Design

## Scope

Only student accounts are affected. Admin and teacher account creation still requires email, and admin/teacher login is not gated by the student email-binding flow.

## Student Email Flow

Teachers may create, edit, or batch import students without an email address. If an email is provided, it must still pass normal email-format validation. New students remain `emailVerified=false`.

When a student logs in and `emailVerified=false`, the app shows the verification gate. If the student already has an email, the student can send a code to that address. If the student has no email, the gate first asks for an email address, sends a verification code to it, stores it on the student record, and then requires the code plus a new password. Successful verification marks the student as verified and replaces the initial password.

If a teacher later changes or clears a student's email, the student is marked unverified so the next login requires verification again.

## Excel Import Flow

The student batch import dialog switches from comma-separated text to an Excel workflow:

- Download a `.xlsx` example template.
- Fill the columns `学号`, `姓名`, `邮箱`, `初始密码`.
- Upload the completed `.xlsx` file.

`学号` and `姓名` are required. `邮箱` and `初始密码` are optional. Empty passwords continue to use `minglog666`.

The frontend parses the workbook into the existing JSON batch-student API. The backend keeps validating each parsed record and returns partial-success details as before.

## Verification

Backend tests should cover optional student email, invalid provided email, email binding during send-code, and teacher/admin not being gated by the student verification UI. Frontend verification should include build plus a smoke test of the login gate and Excel import controls.
