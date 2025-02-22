import PasswordInputField from "@/components/form/fields/password-input.field";
import { isRequired } from "@/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Form, FormSubmit } from "@/components/ui/form";
import { UPDATE_ACCOUNT_PASSWORD } from "@/graphql/mutations/accounts/updateAccountPassword";
import { useMutation } from "@/hooks/useQuery";
import Content from "@/screens/layout/content";
import { toast } from "react-toastify";

type UpdatePasswordFormData = {
  newPassword: string;
  confirmPassword: string;
};

export default function TabUpdatePassword() {
  const [updateAccountPassword] = useMutation(UPDATE_ACCOUNT_PASSWORD);

  const onSubmit = async ({ newPassword }: UpdatePasswordFormData) => {
    try {
      await updateAccountPassword({ variables: { password: newPassword } });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Password updated" />);
    } catch (error) {
      console.error("Error while updating the password: ", error);
    }
  };

  return (
    <Content className="p-2">
      <Card className="m-auto w-full max-w-md">
        <h3 className="leading-6 font-semibold mb-4">Update your password</h3>

        <Form
          onSubmit={async (formData) => {
            const data: UpdatePasswordFormData = {
              newPassword: formData.newPassword.value as string,
              confirmPassword: formData.confirmPassword.value as string,
            };
            await onSubmit(data);
          }}
        >
          <PasswordInputField
            name="newPassword"
            label="New password"
            rules={{
              required: true,
              validate: {
                required: isRequired,
              },
            }}
          />

          <PasswordInputField
            name="confirmPassword"
            label="Confirm password"
            rules={{
              required: true,
              validate: {
                required: isRequired,
                isSamePassword: ({ value }, fieldValues) => {
                  return value === fieldValues.newPassword.value || "Passwords don't match";
                },
              },
            }}
          />

          <FormSubmit>Update password</FormSubmit>
        </Form>
      </Card>
    </Content>
  );
}
