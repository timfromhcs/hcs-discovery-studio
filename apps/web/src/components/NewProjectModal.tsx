import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateProject } from "../api/queries";
import { Button, Field, Input, Modal, Textarea, useToast } from "./ui";

export function NewProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const create = useCreateProject();
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [purpose, setPurpose] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName("");
    setDescription("");
    setPurpose("");
    setError(null);
  };

  const submit = async () => {
    setError(null);
    if (!name.trim()) {
      setError("Give the project a name.");
      return;
    }
    try {
      const project = await create.mutateAsync({ name: name.trim(), description, purpose });
      notify(`Project “${project.name}” created`, "ok");
      reset();
      onClose();
      navigate(`/projects/${project.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the project.");
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="New research project"
      description="A project is the provenance boundary for datasets, compounds, workflows and runs."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button variant="primary" icon="plus" onClick={submit} loading={create.isPending}>
            Create project
          </Button>
        </>
      }
    >
      <div className="form-stack">
        <Field label="Project name" htmlFor="project-name" required error={error}>
          <Input
            id="project-name"
            value={name}
            maxLength={200}
            autoFocus
            placeholder="e.g. Kinase pilot — fragment library"
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) void submit();
            }}
          />
        </Field>
        <Field label="Description" htmlFor="project-description" hint="Optional. What questions is this workspace answering?">
          <Textarea
            id="project-description"
            rows={3}
            maxLength={2000}
            value={description}
            placeholder="Scope, target hypothesis, library source…"
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <Field label="Purpose" htmlFor="project-purpose" hint="Optional. Recorded with the project for provenance.">
          <Input
            id="project-purpose"
            maxLength={2000}
            value={purpose}
            placeholder="e.g. Exploratory prioritisation before assay selection"
            onChange={(event) => setPurpose(event.target.value)}
          />
        </Field>
      </div>
    </Modal>
  );
}
