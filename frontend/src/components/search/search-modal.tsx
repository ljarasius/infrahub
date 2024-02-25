import { Combobox, Dialog, Transition } from "@headlessui/react";
import { ChangeEventHandler, forwardRef, Fragment, ReactNode, useEffect, useState } from "react";
import { Icon } from "@iconify-icon/react";
import { Link, useNavigate } from "react-router-dom";
import { classNames } from "../../utils/common";
import { SearchNodes } from "./search-nodes";
import { useDebounce } from "../../hooks/useDebounce";

type SearchInputProps = {
  className?: string;
  value?: string;
  onChange?: ChangeEventHandler<HTMLInputElement>;
};

const SearchInput = ({ value, onChange, className = "" }: SearchInputProps) => {
  return (
    <div className={classNames("relative", className)}>
      <Icon
        icon="mdi:magnify"
        className="text-lg text-custom-blue-10 absolute inset-y-0 left-0 pl-2 flex items-center"
        aria-hidden="true"
      />

      <input
        placeholder="Search anywhere"
        onChange={onChange}
        value={value}
        className={`
            w-full px-8 py-2
            text-sm leading-5 text-gray-900 placeholder:text-gray-400
            rounded-md border border-gray-300 focus:border-custom-blue-600 focus:ring-custom-blue-600 shadow-sm
          `}
      />
    </div>
  );
};

type SearchModalProps = {
  className?: string;
};
export function SearchModal({ className = "" }: SearchModalProps) {
  let [isOpen, setIsOpen] = useState(false);

  function closeModal() {
    setIsOpen(false);
  }

  function openModal() {
    setIsOpen(true);
  }

  useEffect(() => {
    const onSearchAnywhereShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        openModal();
      }
    };

    document.addEventListener("keydown", onSearchAnywhereShortcut);
    return () => document.removeEventListener("keydown", onSearchAnywhereShortcut);
  }, []);

  return (
    <>
      <div onClick={openModal} className={className}>
        <SearchInput value="" className="w-full max-w-lg" onChange={openModal} />
      </div>

      <Transition appear show={isOpen} as={Fragment}>
        <Dialog onClose={closeModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0">
            <div className="fixed inset-0 bg-gray-600/25" />
          </Transition.Child>

          <div className="fixed inset-0">
            <div className="flex items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95">
                <SearchAnywhere onSelection={closeModal} />
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </>
  );
}

type SearchAnywhereProps = {
  onSelection: (url?: string) => void;
};

const SearchAnywhere = forwardRef<HTMLDivElement, SearchAnywhereProps>(
  ({ onSelection }, forwardedRef) => {
    const navigate = useNavigate();
    const [query, setQuery] = useState("");
    const queryDebounced = useDebounce(query, 300);

    return (
      <Dialog.Panel
        ref={forwardedRef}
        className="w-full max-w-screen-md max-h-[75vh] rounded-2xl bg-gray-50 p-2.5 shadow-xl transition-all flex flex-col"
        data-testid="search-anywhere">
        <Combobox
          onChange={(url: string) => {
            if (url.length === 0) return;

            onSelection(url);
            navigate(url);
          }}>
          <div className="relative">
            <Combobox.Button className="absolute top-2.5 left-0 pl-2 flex items-center">
              <Icon icon="mdi:magnify" className="text-lg text-custom-blue-10" aria-hidden="true" />
            </Combobox.Button>

            <Combobox.Input
              placeholder="Search anywhere"
              onChange={(e) => setQuery(e.target.value)}
              value={query}
              className={`
                w-full px-8 py-2
                text-sm leading-5 text-gray-900 placeholder:text-gray-400
                rounded-md border border-gray-300 focus:border-custom-blue-600 focus:ring-custom-blue-600 shadow-sm
              `}
            />
          </div>

          {queryDebounced && (
            <Combobox.Options static className="mt-2 overflow-x-hidden overflow-y-auto divide-y">
              <SearchNodes query={queryDebounced} />
            </Combobox.Options>
          )}
        </Combobox>
      </Dialog.Panel>
    );
  }
);

interface SearchGroupTitleProps {
  children: ReactNode;
}

export const SearchGroupTitle = ({ children }: SearchGroupTitleProps) => {
  return (
    <Combobox.Option
      value=""
      disabled
      className="text-xxs mb-1 mt-2 font-semibold text-gray-500 flex items-center">
      {children}
    </Combobox.Option>
  );
};

interface SearchResultItemProps {
  children: ReactNode;
  to: string;
}
export const SearchResultItem = ({ children, to }: SearchResultItemProps) => {
  return (
    <Combobox.Option
      as={Link}
      value={to}
      to={to}
      className={({ active }) => `flex gap-1 text-sm py-3 ${active ? "bg-slate-200" : ""}`}>
      {children}
    </Combobox.Option>
  );
};
