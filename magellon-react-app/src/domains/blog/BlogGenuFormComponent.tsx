import React from 'react'
import GenuForm from "../../libs/genuform/GenuForm.tsx";
import GenuFieldFormItem from "../../libs/genuform/GenuFieldFormItem.tsx";
import {IBlog,Blog} from "./Blog.Model.ts";

export default function BlogGenuFormComponent() {
    console.log("BlogGenuFormComponent");
    const blog:IBlog = {
        // id: data.id, // Include ID for updates (assuming it's available in your form data)
        id: 125, // Include ID for updates (assuming it's available in your form data)
        title: "salam",
        body: "Chetory shoma",
    };
    const theBlog = new Blog(blog);

    return (
        <div>
            <GenuForm name="personForm" caption="Person Form" entity={theBlog}>
                {/*<GenuTextBoxEditor name="firstName" caption="First Name:" value={2}/>*/}
                <GenuFieldFormItem caption={"Title"} widget="GenuTextBoxEditor" name={"title "} info={"enter your last name"} error={"Be carefull"} warning={"Watch out"}/>
                <GenuFieldFormItem caption={"Body"} widget="GenuTextBoxEditor" name={"body"} info={"enter your age"}   error={"Be carefull"} warning={"Watch out"}/>
            </GenuForm>
        </div>
    )
}
