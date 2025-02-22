import {
  DynamicFieldProps,
  FormAttributeValue,
  FormRelationshipValue,
  RelationshipValueFromPool,
} from "@/components/form/type";
import { getUpdateMutationFromFormData } from "@/components/form/utils/mutations/getUpdateMutationFromFormData";
import { describe, expect } from "vitest";
import { buildField } from "./getCreateMutationFromFormData.test";

describe("getUpdateMutationFromFormData - test", () => {
  it("returns empty if there is no fields in form", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [];
    const formData: Record<string, FormAttributeValue> = {};

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps value if it's from the user", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "test-value" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "test-value" },
    });
  });

  it("set value to null if it's from the user and is an empty string", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("set attribute to null if it's from the user and value is null", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: null },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: null },
    });
  });

  it("set relationship to null if it's from the user and value is null", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "relationship1",
        type: "relationship",
        defaultValue: {
          source: { type: "schema" },
          value: null,
        },
      }),
    ];
    const formData: Record<string, FormRelationshipValue> = {
      relationship1: { source: { type: "user" }, value: null },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      relationship1: null,
    });
  });

  it("removes field if value and source are not updated", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "old-value" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "old-value" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({});
  });

  it("keeps field if source is updated", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "schema" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "user" }, value: "value1" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { value: "value1" },
    });
  });

  it("keeps field if source change from user to pool", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        type: "relationship",
        defaultValue: {
          source: { type: "user" },
          value: { id: "value1", display_label: "value1", __typename: "FakeResource" },
        },
      }),
    ];
    const formData: Record<string, RelationshipValueFromPool> = {
      field1: {
        source: {
          type: "pool",
          label: "test name pool",
          id: "pool-id",
          kind: "FakeResourcePool",
        },
        value: {
          from_pool: { id: "pool-id" },
        },
      },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: {
        from_pool: { id: "pool-id" },
      },
    });
  });

  it("set is_default: true if field if value is from profile", () => {
    // GIVEN
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: {
        source: {
          type: "profile",
          kind: "FakeProfileKind",
          id: "profile-id",
          label: "Profile 1",
        },
        value: "profile1",
      },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { is_default: true },
    });
  });

  it("set is_default: true if field if value is from schema", () => {
    const fields: Array<DynamicFieldProps> = [
      buildField({
        name: "field1",
        defaultValue: { source: { type: "user" }, value: "value1" },
      }),
    ];
    const formData: Record<string, FormAttributeValue> = {
      field1: { source: { type: "schema" }, value: "value2" },
    };

    // WHEN
    const mutationData = getUpdateMutationFromFormData({ fields, formData });

    // THEN
    expect(mutationData).to.deep.equal({
      field1: { is_default: true },
    });
  });
});
